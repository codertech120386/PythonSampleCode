from sqlalchemy.orm import joinedload
from utils.ses import send_project_resourcing_email
import datetime
from utils.exceptions import InvalidRequest
from freelancer_auth.models import FreelancerNoteModel, FreelancerModel
from auth.models import UserModel
import os
from .models import (
    MasterProjectModel, ProjectLocationModel, ProjectResourcingModel, ProjectTeamMemberModel, ProjectScopeLinkModel, ProjectScopeFileModel,
    ProjectClientModel, ProjectCandidateMapModel, ProjectScaleMapModel, ProjectCriteriaMapModel, ProjectStakeholdersModel, ProjectDirectorsModel,
    ProjectNoteModel
)


def get_project_by_id(session, id):
    return session.query(MasterProjectModel).options(
        joinedload('members'),
        joinedload('directors'),
        joinedload('candidates'),
        joinedload('stakeholders'),
        joinedload('scope_files'),
        joinedload('scope_links'),
        joinedload('note_list')
    ).filter_by(id=id).scalar()


def get_project_resourcing(session, id):
    return session.query(ProjectResourcingModel).options(
        joinedload('segment'),
        joinedload('sub_segment'),
        joinedload('rating_criteria'),
        joinedload('director'),
        joinedload('lead')
    ).filter_by(project_id=id).scalar()


def get_project_members(session, id):
    return session.query(ProjectTeamMemberModel).options(
        joinedload('member')
    ).filter_by(project_id=id).all()


def get_project_client_map(session, id):
    return session.query(ProjectClientModel).options(
        joinedload('client'),
        joinedload('stakeholder')
    ).filter_by(project_id=id).scalar()


def get_project_location_details(session, id):
    return session.query(ProjectLocationModel).filter_by(project_id=id).scalar()


def add_projection_location_details(session, *args, **kwargs):
    location = session.query(ProjectLocationModel).filter_by(project_id=kwargs['project_id']).scalar()
    if not location:
        location = ProjectLocationModel(project_id=kwargs['project_id'])
        session.add(location)
        session.flush()
    for key in [
            'location', 'location_type', 'looking_for', 'start_date', 'duration_count',
            'duration_unit', 'budget_currency', 'budget_amount', 'enable_full_time', 'expected_annual_salary',
            'enable_fixed_rate_projects', 'expected_monthly_rate', 'enable_full_day_projects', 'expected_daily_rate',
            'enable_hourly_projects', 'expected_hourly_rate', 'min_hours'
             ]:
        setattr(location, key, kwargs[key])


def add_project_resourcing(session, *args, **kwargs):
    project = get_project_by_id(session, kwargs['project_id'])
    resourcing = session.query(ProjectResourcingModel).filter_by(project_id=kwargs['project_id']).scalar()
    if not resourcing:
        resourcing = ProjectResourcingModel(project_id=kwargs['project_id'])
        session.add(resourcing)
        session.flush()
    i_director, i_lead = resourcing.director_id, resourcing.lead_id
    team_members = [m.member_id for m in session.query(ProjectTeamMemberModel).filter_by(
        project_id=kwargs['project_id']
    ).all()]
    for key in ['segment_id', 'sub_segment_id', 'rating_criteria_id', 'director_id', 'lead_id', 'notes']:
        setattr(resourcing, key, kwargs[key])
    session.query(ProjectTeamMemberModel).filter_by(
        project_id=kwargs['project_id']
    ).delete()

    for member_id in kwargs['member_ids']:
        session.add(ProjectTeamMemberModel(project_id=kwargs['project_id'], member_id=member_id))
        session.flush()

    if not i_director == kwargs['director_id']:
        user = session.query(UserModel).filter_by(id=kwargs['director_id']).scalar()
        send_project_resourcing_email(user.email, project.name, "Director")

    if not i_lead == kwargs['lead_id']:
        user = session.query(UserModel).filter_by(id=kwargs['lead_id']).scalar()
        send_project_resourcing_email(user.email, project.name, "Lead")

    for member in kwargs['member_ids']:
        if member not in team_members:
            user = session.query(UserModel).filter_by(id=member).scalar()
            send_project_resourcing_email(user.email, project.name, "Team Member")


def add_project_scope_link(session, project_id, name, link, is_scope):
    if not session.query(ProjectScopeLinkModel).filter_by(project_id=project_id, document_name=name, link=link).all():
        session.add(ProjectScopeLinkModel(project_id=project_id, document_name=name, link=link, is_scope=is_scope))
        session.flush()


def clear_project_scope_files(session, project_id):
    session.query(ProjectScopeFileModel).filter_by(project_id=project_id).delete()


def clear_project_scope_links(session, project_id):
    session.query(ProjectScopeLinkModel).filter_by(project_id=project_id).delete()


def clear_project_stakeholders(session, project_id):
    session.query(ProjectStakeholdersModel).filter_by(project_id=project_id).delete()


def clear_project_members(session, project_id):
    session.query(ProjectTeamMemberModel).filter_by(project_id=project_id).delete()


def clear_project_directors(session, project_id):
    session.query(ProjectDirectorsModel).filter_by(project_id=project_id).delete()


def add_project_scope_file(session, project_id, link):
    name = os.path.basename(link)
    if not session.query(ProjectScopeFileModel).filter_by(project_id=project_id, name=name, link=link).all():
        session.add(ProjectScopeFileModel(project_id=project_id, name=name, link=link))
        session.flush()


def add_stakeholder(session, project_id, stakeholder_id):
    if not session.query(ProjectStakeholdersModel).filter_by(project_id=project_id, stakeholder_id=stakeholder_id).all():
        session.add(ProjectStakeholdersModel(project_id=project_id, stakeholder_id=stakeholder_id))
        session.flush()


def add_team_member(session, project_id, member_id):
    if not session.query(ProjectTeamMemberModel).filter_by(project_id=project_id, member_id=member_id).all():
        session.add(ProjectTeamMemberModel(project_id=project_id, member_id=member_id))
        session.flush()


def add_director(session, project_id, director_id):
    if not session.query(ProjectDirectorsModel).filter_by(project_id=project_id, director_id=director_id).all():
        session.add(ProjectDirectorsModel(project_id=project_id, director_id=director_id))
        session.flush()


def map_project_client(session, project_id, client_id, poc_id):
    # remove earlier mapping
    session.query(ProjectClientModel).filter_by(
        project_id=project_id
    ).delete()
    # add new mapping
    session.add(ProjectClientModel(
        project_id=project_id, client_id=client_id, stakeholder_id=poc_id
    ))
    session.flush()


def add_project_candidate(session, project_id, freelancer_id, stage="Longlist"):
    if not session.query(MasterProjectModel).filter_by(id=project_id).scalar():
        raise InvalidRequest("Project id does not exist")
    pc = session.query(ProjectCandidateMapModel).filter_by(project_id=project_id, freelancer_id=freelancer_id).scalar()
    if not pc:
        pc = ProjectCandidateMapModel(
            project_id=project_id,
            freelancer_id=freelancer_id,
            stage=stage
        )
        session.add(pc)
        session.flush()
    return pc.id


def add_project_candidates(session, project_ids, freelancer_id, stage="Longlist"):
    from freelancer_new.services import change_freelancer_status
    candidates = []
    change_freelancer_status(session, freelancer_id, "Accepted")
    for project_id in project_ids:
        pc = session.query(ProjectCandidateMapModel).filter_by(project_id=project_id, freelancer_id=freelancer_id).scalar()
        if not pc:
            pc = ProjectCandidateMapModel(
                project_id=project_id,
                freelancer_id=freelancer_id,
                stage=stage
            )
            session.add(pc)
            session.flush()
        candidates.append(pc)
    try:
        from utils.index import insert_freelancer
        insert_freelancer(freelancer_id)
    except:
        print("failted to re index {}".format(freelancer_id))
    return candidates


def reject_project_candidate(session, candidate_ids):
    candidates = get_candidates_with_id(session, candidate_ids)
    for candidate in candidates:
        candidate.rejected = True
    session.flush()


def edit_project_candidate(session, candidate_id, **kwargs):
    candidates = get_candidates_with_id(session, [candidate_id])
    if not candidates:
        raise InvalidRequest("candidate id doesnt exist")
    for candidate in candidates:
        for key, val in kwargs.items():
            setattr(candidate, key, val)
            freelancer = session.query(FreelancerModel).filter_by(id=candidate.freelancer_id).first()
            if kwargs['stage'] == "Longlist":
                freelancer.interview_status = "Pending"
        try:
            from utils.index import insert_freelancer
            insert_freelancer(candidate.freelancer_id)
        except:
            print("failted to re index {}".format(candidate.freelancer_id))

    session.flush()


def update_project_settings(session, project_id, hiring_stage_id):
    project = get_project_by_id(session, project_id)
    project.hiring_stage_id = hiring_stage_id
    session.flush()


def get_candidates_with_id(session, ids):
    return session.query(ProjectCandidateMapModel).filter(ProjectCandidateMapModel.id.in_(ids)).all()


def get_candidates_for_freelancer(session, freelancer_id):
    return session.query(ProjectCandidateMapModel).filter_by(freelancer_id=freelancer_id).all()


def set_project_scales(session, project_id, scale_ids):
    session.query(ProjectScaleMapModel).filter_by(
        project_id=project_id
    ).delete()
    for scale_id in scale_ids:
        session.add(
            ProjectScaleMapModel(project_id=project_id, scale_id=scale_id)
        )
    session.flush()


def set_project_criterias(session, project_id, criteria_ids):
    session.query(ProjectCriteriaMapModel).filter_by(
        project_id=project_id
    ).delete()
    for criteria_id in criteria_ids:
        session.add(
            ProjectCriteriaMapModel(project_id=project_id, criteria_id=criteria_id)
        )
    session.flush()


def get_project_scales(session, project_id):
    return [m.scale_id for m in session.query(ProjectScaleMapModel).filter_by(
        project_id=project_id
    ).all()]


def get_project_criterias(session, project_id):
    return [m.criteria_id for m in session.query(ProjectCriteriaMapModel).filter_by(
        project_id=project_id
    ).all()]


def add_project_note(session, admin_id, note, project_id):
    if not session.query(MasterProjectModel).filter_by(id=project_id).scalar():
        raise InvalidRequest("project id does not exist")
    fnote = ProjectNoteModel(
        project_id=project_id,
        admin_id=admin_id,
        note=note
    )
    session.add(fnote)
    session.commit()


def edit_project_note(session, admin_id, note_id, note):
    note_obj = session.query(ProjectNoteModel).filter_by(id=note_id).scalar()
    if not note_obj:
        raise InvalidRequest("note id does not exist")
    if not note_obj.admin_id:
        note_obj.admin_id = admin_id
    elif note_obj.admin_id != admin_id:
        raise InvalidRequest("You don't have permissions to edit this note")
    note_obj.note = note
    note_obj.created_at = datetime.dateime.utcnow()
    session.commit()


def delete_project_note(session, admin_id, note_id):
    note = session.query(ProjectNoteModel).filter_by(id=note_id).scalar()
    if not note:
        raise InvalidRequest("note id does not exist")
    if not note.admin_id:
        note.admin_id = admin_id
    elif note.admin_id != admin_id:
        raise InvalidRequest("You don't have permissions to edit this note")
    session.query(ProjectNoteModel).filter_by(id=note_id).delete()
    session.commit()


def add_freelancer_note(session, freelancer_id, admin_id, note, project_id=None):
    if not session.query(FreelancerModel).filter_by(id=freelancer_id).scalar():
        raise InvalidRequest("Freelancer id does not exist")
    fnote = FreelancerNoteModel(
        freelancer_id=freelancer_id,
        admin_id=admin_id,
        note=note
    )
    if project_id:
        fnote.project_id = project_id
    session.add(fnote)
    session.commit()


def edit_freelancer_note(session, admin_id, note_id, note):
    note_obj = session.query(FreelancerNoteModel).filter_by(id=note_id).scalar()
    if not note_obj:
        raise InvalidRequest("note id does not exist")
    if not note_obj.admin_id:
        note_obj.admin_id = admin_id
    elif note_obj.admin_id != admin_id:
        raise InvalidRequest("You don't have permissions to edit this note")
    note_obj.note = note
    note_obj.created_at = datetime.dateime.utcnow()
    session.commit()


def delete_freelancer_note(session, admin_id, note_id):
    note = session.query(FreelancerNoteModel).filter_by(id=note_id).scalar()
    if not note:
        raise InvalidRequest("note id does not exist")
    if not note.admin_id:
        note.admin_id = admin_id
    elif note.admin_id != admin_id:
        raise InvalidRequest("You don't have permissions to edit this note")
    session.query(FreelancerNoteModel).filter_by(id=note_id).delete()
    session.commit()


def update_candidate_quote(session, project_id, freelancer_id, rate_unit, rate_amount, rate_currency):
    cmap = session.query(ProjectCandidateMapModel).filter_by(project_id=project_id, freelancer_id=freelancer_id).scalar()
    if not cmap:
        raise InvalidRequest("Candidate does not exit")
    cmap.rate_unit = rate_unit
    cmap.rate_amount = rate_amount
    cmap.rate_currency = rate_currency
    session.commit()
