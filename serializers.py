import re
import json
from utils.db import get_session
from utils.es_conn import es
from utils.string_utils import lower_plain_str
from elasticsearch import helpers
from clients.models import ClientMasterModel
from auth.models import UserModel
from .models import MasterProjectModel, ProjectDirectorsModel, ProjectTeamMemberModel, ProjectCandidateMapModel


SYNONYM_ANALYSER = {
    "analysis": {
        "analyzer": {
            "default": {
                "tokenizer": "whitespace",
                "filter": ["synonym", "lowercase"]
            }
        },
        "filter": {
            "synonym": {
                "type": "synonym",
                "synonyms": ["oil,petrol"],
                "ignore_case": True
            }
        }
    }
}


def get_project_json(session, project):
    print(project.city, project.country)

    data = {
        "project_title": project.name,
        "id": project.id,
        "project_type": project.project_type,
        "project_status": project.project_status,
        "background": project.background,
        "notes": project.notes,
        "city": project.city,
        "country": project.country,
        "client_type": project.client_type,
        "closed_quarter": project.closed_quarter,
        "duration": "{} {}".format(project.duration_count, project.duration_unit),
        "budget": "{} {} {}".format(project.budget_amount, project.budget_currency, project.budget_unit),
        "client_name": project.client_id,
        "skills": [s.name for s in project.get_attributes(session, "expertise")],
        "sectors": [s.name for s in project.get_attributes(session, "sector")],
        "freelancer_location_type": project.freelancer_location_type,
        "educational_background": project.educational_background,
        "segment": project.segment,
        "sub_segment": project.sub_segment,
        "is_client_confidential": project.is_client_confidential
    }
    if project.project_start_date:
        data["project_start_date"] = str(project.project_start_date)
    data["directors"] = [m.director_id for m in session.query(ProjectDirectorsModel).filter_by(project_id=project.id).all()]
    data["members"] = [m.member_id for m in session.query(ProjectTeamMemberModel).filter_by(project_id=project.id).all()]
    return data


def index_freelancer_projects(freelancer_id):
    session = get_session()
    pids = [c.project_id for c in session.query(ProjectCandidateMapModel).filter_by(freelancer_id=freelancer_id).all()]
    projects = session.query(MasterProjectModel).filter(MasterProjectModel.id.in_(pids)).all()
    index_all_projects(projects, keep_index=True)
    session.close()


def index_project(project_id):
    import datetime
    session = get_session()
    projects = session.query(MasterProjectModel).filter(MasterProjectModel.id.in_([project_id])).all()
    for project in projects:
        project.modified_at = datetime.datetime.utcnow()
        session.commit()
    freelancer_ids = [c.freelancer_id for c in session.query(ProjectCandidateMapModel).filter_by(project_id=project_id).all()]
    index_all_projects(projects, keep_index=True)
    session.close()
    return freelancer_ids


def remove_trailing_special(s):
    return re.sub(r'([^\w\s]|_)+(?=\s|$)', '', s) if s else s


def val_to_str(v):
    if isinstance(v, list):
        return " ".join([str(a) for a in v])
    return remove_trailing_special(str(v))


def index_all_projects(projects=None, keep_index=False):
    from utils.index import push_doc

    session = get_session()
    if es.indices.exists('project') and not keep_index:
        es.indices.delete('project')
        settings = {
            "settings": SYNONYM_ANALYSER
        }
        es.indices.create('project', body=settings)

    bodies = []
    clients = {c.id: c.name for c in session.query(ClientMasterModel).all()}
    users = {u.id: u.name for u in session.query(UserModel).all()}
    if not projects:
        projects = session.query(MasterProjectModel).all()
    for project in projects:
        doc = get_project_json(session, project)
        doc["client_name"] = clients.get(doc['client_name'], "")
        if doc["client_name"]:
            doc["project_title"] = "{} - {}".format(doc["client_name"], doc["project_title"])
        doc["ac_search_field"] = lower_plain_str(doc['project_title'])
        doc["directors"] = [users.get(d, "") for d in doc['directors']]
        doc["members"] = [users.get(d, "") for d in doc['members']]
        doc["full_text"] = " ".join([val_to_str(v) for v in doc.values()])
        doc.update({
            '_index': 'project',
            '_type': 'project',
            '_id': project.id
        })
        bodies.append(doc)

        kdoc = {
            "keyword": doc["project_title"],
            "keyword_type": "project",
            "keyword_id": project.id,
            "ac_search_field": lower_plain_str(doc["project_title"])
        }

        kdoc_id = "project_{}".format(project.id)

        push_doc(kdoc, kdoc_id, "keyword", "keyword")

    res = helpers.bulk(es, bodies, chunk_size=1000, request_timeout=200)
    print(res)
    session.commit()
    session.close()
