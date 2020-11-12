import graphene
import os
import datetime
from sqlalchemy.orm import joinedload
from utils.db import get_session
from utils.string_utils import lower_plain_str
from utils.authorization import verify_admin, verify_freelancer
from utils.exceptions import InvalidRequest
from utils.elapsed import elapsed_time_str
from admin.api import Admin
from clients.query import ClientMaster, POC
from clients.services import fetch_client
from freelancer_profile.api import Freelancer, load_freelancer
from freelancer_auth.models import FreelancerModel
from process.models import TemplateModel, StageModel
from location.query import Place
from process.api import Template
from scales.api import Scale, ScaleCritera
from .models import MasterProjectModel, ProjectSegmentModel, ProjectSubSegmentModel, ProjectRatingCriteriaModel, ProjectCandidateMapModel, ProjectDirectorsModel, ProjectTeamMemberModel
from .services import (
    get_project_by_id, get_project_resourcing, get_project_members, get_project_client_map, get_candidates_for_freelancer, get_project_criterias,
    get_project_scales, get_project_location_details
)


class MasterProjectAttribute(graphene.ObjectType):
    id = graphene.Int()
    name = graphene.String()

    def __init__(self, obj):
        self.obj = obj

    def resolve_id(self, info, *args, **kwargs):
        return self.obj.id

    def resolve_name(self, info, *args, **kwargs):
        return self.obj.name


class ProjectSmall(graphene.ObjectType):
    id = graphene.Int()
    name = graphene.String()
    assigned = graphene.Boolean()
    candidate_status = graphene.String()
    client_name = graphene.String()
    project_stage = graphene.String()
    expertise = graphene.List(MasterProjectAttribute)
    sectors = graphene.List(MasterProjectAttribute)
    hiring_stages = graphene.Field(Template)

    def __init__(self, obj, assigned=False, stage=None):
        self.obj = obj
        self.assigned = assigned
        self.candidate_status = stage

    def resolve_id(self, info):
        return self.obj.id

    def resolve_assigned(self, info):
        return self.assigned

    def resolve_candidate_status(self, info):
        return self.candidate_status

    def resolve_name(self, info):
        return self.obj.name

    def resolve_project_stage(self, info, *args, **kwargs):
        return "Matching" if not self.obj.project_status else self.obj.project_status

    def resolve_client_name(self, info):
        session = get_session()
        client = fetch_client(session, self.obj.client_id)
        session.close()
        return client.name if client else ""

    def resolve_hiring_stages(self, info, *args, **kwargs):
        session = get_session()
        t = session.query(TemplateModel).filter_by(id=1).scalar()
        if t:
            return Template(t)
        else:
            return None
        session.close()

    def resolve_expertise(self, info, *args, **kwargs):
        session = get_session()
        attrs = self.obj.get_attributes(session, 'expertise')
        session.close()
        return [MasterProjectAttribute(attr) for attr in attrs]

    def resolve_sectors(self, info, *args, **kwargs):
        session = get_session()
        attrs = self.obj.get_attributes(session, 'sector')
        session.close()
        return [MasterProjectAttribute(attr) for attr in attrs]

    @classmethod
    def assign_project_autocomplete(cls, *args, **kwargs):
        from utils.index import search
        verify_admin(kwargs['token'])
        freelancer_id = kwargs['freelancer_id']
        session = get_session()
        candidates = get_candidates_for_freelancer(session, freelancer_id)
        project_map = {c.project_id: c.stage for c in candidates}
        q = lower_plain_str(kwargs.get("q", ""))
        start = kwargs.get("start", 0)
        end = kwargs.get("end", 10)
        hits = search(q, "project", fields=['ac_search_field']).hits[start:end]
        ids = [h.id for h in hits]
        projects = session.query(MasterProjectModel).filter(MasterProjectModel.id.in_(ids)).all()
        ans = [ProjectSmall(p, p.id in project_map, project_map.get(p.id, None)) for p in projects]
        session.close()
        return ans


class ProjectCandidate(graphene.ObjectType):
    id = graphene.Int()
    freelancer = graphene.Field(Freelancer)
    added_on = graphene.DateTime()
    status = graphene.String()
    rate_unit = graphene.String()
    rate_currency = graphene.String()
    rate_amount = graphene.Int()
    project = graphene.Field(ProjectSmall)
    is_active = graphene.Boolean()

    def __init__(self, obj, project_id=None):
        self.obj = obj
        self.project_id = project_id

    def resolve_id(self, info):
        return self.obj.id

    def resolve_rate_currency(self, info):
        return self.obj.rate_currency if self.obj.rate_currency else "INR"

    def resolve_is_active(self, info):
        return not self.obj.rejected

    def resolve_rate_unit(self, info):
        return self.obj.rate_unit

    def resolve_rate_amount(self, info):
        return self.obj.rate_amount

    def resolve_freelancer(self, info):
        session = get_session()
        freelancer = load_freelancer(session, self.obj.freelancer_id)
        session.close()
        return Freelancer(freelancer, project_id=self.project_id, show_full=True)

    def resolve_added_on(self, info):
        return self.obj.added_on

    def resolve_status(self, info):
        return self.obj.stage

    def resolve_project(self, info):
        session = get_session()
        project = get_project_by_id(session, self.obj.project_id)
        session.close()
        return ProjectSmall(project)

    @staticmethod
    def freelancer_projects(*args, **kwargs):
        if 'freelancer_id' in kwargs:
            verify_admin(kwargs['token'])
            freelancer_id = kwargs['freelancer_id']
        else:
            freelancer, _ = verify_freelancer(kwargs['token'])
            freelancer_id = freelancer.id
        session = get_session()
        candidates = get_candidates_for_freelancer(session, freelancer_id)
        session.close()
        return [ProjectCandidate(c) for c in candidates]


class ScopeFile(graphene.ObjectType):
    id = graphene.Int()
    name = graphene.String()
    link = graphene.String()
    is_scope = graphene.Boolean()

    def __init__(self, obj):
        self.obj = obj

    def resolve_id(self, info):
        return self.obj.id

    def resolve_name(self, info):
        return self.obj.name

    def resolve_link(self, info):
        return self.obj.link

    def resolve_is_scope(self, info):
        return self.obj.is_scope


class ScopeLink(graphene.ObjectType):
    id = graphene.Int()
    name = graphene.String()
    link = graphene.String()
    is_scope = graphene.Boolean()

    def __init__(self, obj):
        self.obj = obj

    def resolve_id(self, info):
        return self.obj.id

    def resolve_name(self, info):
        return self.obj.document_name

    def resolve_link(self, info):
        return self.obj.link

    def resolve_is_scope(self, info):
        return self.obj.is_scope


class ClientMap(graphene.ObjectType):
    client = graphene.Field(ClientMaster)
    stakeholder = graphene.Field(POC)

    def __init__(self, obj):
        self.obj = obj

    def resolve_client(self, info):
        return ClientMaster(self.obj.client)

    def resolve_stakeholder(self, info):
        return POC(self.obj.stakeholder)


class ResourceConstant(graphene.ObjectType):
    id = graphene.Int()
    name = graphene.String()

    def __init__(self, obj):
        self.obj = obj

    def resolve_id(self, info):
        return self.obj.id

    def resolve_name(self, info):
        return self.obj.name


class ProjectResourcing(graphene.ObjectType):
    segment = graphene.Field(ResourceConstant)
    rating_criteria = graphene.Field(ResourceConstant)
    sub_segment = graphene.Field(ResourceConstant)
    director = graphene.Field(Admin)
    lead = graphene.Field(Admin)
    members = graphene.List(Admin)
    notes = graphene.String()

    def __init__(self, obj, members):
        self.obj = obj
        self.member_objs = members

    def resolve_segment(self, info):
        return ResourceConstant(self.obj.segment)

    def resolve_rating_criteria(self, info):
        return ResourceConstant(self.obj.rating_criteria)

    def resolve_sub_segment(self, info):
        return ResourceConstant(self.obj.sub_segment)

    def resolve_notes(self, info):
        return self.obj.notes

    def resolve_director(self, info):
        return Admin(self.obj.director)

    def resolve_lead(self, info):
        return Admin(self.obj.lead)

    def resolve_members(self, info):
        return [Admin(m.member) for m in self.member_objs]


class ProjectLocation(graphene.ObjectType):
    location = graphene.String()
    looking_for = graphene.String()
    duration_count = graphene.Int()
    duration_unit = graphene.String()
    location_type = graphene.String()
    start_date = graphene.Date()
    budget_currency = graphene.String()
    budget_amount = graphene.Int()
    enable_full_time = graphene.Boolean()
    expected_annual_salary = graphene.Int()
    enable_fixed_rate_projects = graphene.Boolean()
    expected_monthly_rate = graphene.Int()
    enable_full_day_projects = graphene.Boolean()
    expected_daily_rate = graphene.Int()
    enable_hourly_projects = graphene.Boolean()
    expected_hourly_rate = graphene.Int()
    min_hours = graphene.Int()

    def __init__(self, obj):
        self.obj = obj

    def resolve_location(self, info):
        return self.obj.location

    def resolve_looking_for(self, info):
        return self.obj.looking_for

    def resolve_duration_count(self, info):
        return self.obj.duration_count

    def resolve_duration_unit(self, info):
        return self.obj.duration_unit

    def resolve_location_type(self, info):
        return self.obj.location_type

    def resolve_start_date(self, info):
        return self.obj.start_date

    def resolve_budget_currency(self, info):
        return self.obj.budget_currency

    def resolve_budget_amount(self, info):
        return self.obj.budget_amount

    def resolve_enable_full_time(self, info, *args, **kwargs):
        return self.obj.enable_full_time

    def resolve_expected_annual_salary(self, info, *args, **kwargs):
        return self.obj.expected_annual_salary

    def resolve_enable_fixed_rate_projects(self, info, *args, **kwargs):
        return self.obj.enable_fixed_rate_projects

    def resolve_expected_monthly_rate(self, info, *args, **kwargs):
        return self.obj.expected_monthly_rate

    def resolve_enable_full_day_projects(self, info, *args, **kwargs):
        return self.obj.enable_full_day_projects

    def resolve_expected_daily_rate(self, info, *args, **kwargs):
        return self.obj.expected_daily_rate

    def resolve_enable_hourly_projects(self, info, *args, **kwargs):
        return self.obj.enable_hourly_projects

    def resolve_expected_hourly_rate(self, info, *args, **kwargs):
        return self.obj.expected_hourly_rate

    def resolve_min_hours(self, info, *args, **kwargs):
        return self.obj.min_hours


class ProjectNote(graphene.ObjectType):
    time_elapsed = graphene.String()
    id = graphene.Int()
    created_by = graphene.String()
    note = graphene.String()

    def __init__(self, obj):
        self.obj = obj

    def resolve_id(self, info, *args, **kwargs):
        return self.obj.id

    def resolve_created_by(self, info, *args, **kwargs):
        from auth.models import UserModel
        session = get_session()
        user = session.query(UserModel).filter_by(id=self.obj.admin_id).scalar()
        session.close()
        return user.email.split("@")[0]

    def resolve_note(self, info, *args, **kwargs):
        return self.obj.note

    def resolve_time_elapsed(self, info, *args, **kwargs):
        return elapsed_time_str(self.obj.created_at)


class CandidateCount(graphene.ObjectType):
    count = graphene.Int()
    stage_id = graphene.Int()
    stage_name = graphene.String()

    def __init__(self, stage_id, stage_name, count):
        self.stage_id = stage_id
        self.stage_name = stage_name
        self.count = count

    def resolve_count(self, info):
        return self.count

    def resolve_stage_id(self, info):
        return self.stage_id

    def resolve_stage_name(self, info):
        return self.stage_name


def get_project_title(p, cmap):
    if p.client_id in cmap:
        return "{} - {}".format(cmap[p.client_id], p.name)
    else:
        return p.name


def typeahead_sorter(items, q):
    def starts(i):
        return not str(i.project_title).upper().startswith(q.upper())
    return sorted(items, key=starts)


class ProjectAutoComplete(graphene.ObjectType):
    id = graphene.Int()
    name = graphene.String()
    client = graphene.String()

    def __init__(self, hit):
        self.hit = hit

    def resolve_id(self, info):
        return self.hit.id

    def resolve_name(self, info):
        return self.hit.project_title

    def resolve_client(self, info):
        return self.hit.client_name


class MasterProject(graphene.ObjectType):
    id = graphene.Int()
    score = graphene.Float()
    time_elapsed = graphene.String()
    created_by = graphene.String()
    created_at = graphene.String()
    client_type = graphene.String()
    closed_quarter = graphene.String()
    closed_year = graphene.String()
    modified_at = graphene.String()
    no_of_freelancers = graphene.Int()
    location = graphene.Field(Place)
    name = graphene.String()
    project_type = graphene.String()
    background = graphene.String()
    notes = graphene.String()
    hiring_stages = graphene.Field(Template)
    client_id = graphene.Int()
    client = graphene.Field(ClientMaster)
    duration_unit = graphene.String()
    duration_count = graphene.Int()
    budget_currency = graphene.String()
    budget_amount = graphene.Int()
    budget_unit = graphene.String()
    budget_notes = graphene.String()
    min_years_experience = graphene.Int()
    max_years_experience = graphene.Int()
    expertise = graphene.List(MasterProjectAttribute)
    sectors = graphene.List(MasterProjectAttribute)
    scope_files = graphene.List(graphene.String)
    scope_links = graphene.List(ScopeLink)
    members = graphene.List(Admin)
    directors = graphene.List(Admin)
    stakeholders = graphene.List(POC)
    project_stage = graphene.String()
    candidates = graphene.List(
        ProjectCandidate,
        start=graphene.Int(default_value=0),
        end=graphene.Int(default_value=9),
        status=graphene.String(default_value="All"),
        sort=graphene.String(default_value=None),
    )
    total_candidates = graphene.Int()
    candidate_counts = graphene.List(CandidateCount)
    note_list = graphene.List(ProjectNote)
    freelancer_location_type = graphene.String()
    educational_background = graphene.String()
    project_start_date = graphene.String()
    segment = graphene.String()
    sub_segment = graphene.String()
    is_client_confidential = graphene.Boolean()
    sharepoint_link = graphene.String()

    def __init__(self, obj, config=dict(), score=0):
        self.obj = obj
        self.config = config
        self.score = score

    def resolve_id(self, info, *args, **kwargs):
        return self.obj.id

    def resolve_score(self, info, *args, **kwargs):
        return self.score

    def resolve_client_type(self, info, *args, **kwargs):
        return self.obj.client_type

    def resolve_closed_quarter(self, info, *args, **kwargs):
        return self.obj.closed_quarter

    def resolve_closed_year(self, info, *args, **kwargs):
        return self.obj.closed_year

    def resolve_created_by(self, info, *args, **kwargs):
        if not self.obj.admin_id:
            return ""
        from auth.models import UserModel
        session = get_session()
        user = session.query(UserModel).filter_by(id=self.obj.admin_id).scalar()
        session.close()
        return user.name if user.name else user.email.split("@")[0]

    def resolve_location(self, info, *args, **kwargs):
        if not self.obj.location_id:
            return None
        session = get_session()
        place = Place.detail(session, self.obj.location_id)
        session.close()
        return place

    def resolve_created_at(self, info, *args, **kwargs):
        return self.obj.created_at.strftime("%d %B %Y, %I:%M %p") if self.obj.created_at else ""

    def resolve_modified_at(self, info, *args, **kwargs):
        return self.obj.modified_at.strftime("%d %B %Y, %I:%M %p") if self.obj.modified_at else ""

    def resolve_total_candidates(self, info, *args, **kwargs):
        return len(self.obj.candidates)

    def resolve_hiring_stages(self, info, *args, **kwargs):
        session = get_session()
        t = session.query(TemplateModel).filter_by(id=1).scalar()
        if t:
            return Template(t)
        else:
            return None
        session.close()

    def resolve_no_of_freelancers(self, info, *args, **kwargs):
        return self.obj.no_of_freelancers

    def resolve_name(self, info, *args, **kwargs):
        return self.obj.name

    def resolve_client_id(self, info, *args, **kwargs):
        return self.obj.client_id

    def resolve_client(self, info, *args, **kwargs):
        return ClientMaster.from_id(id=self.obj.client_id)

    def resolve_duration_count(self, info, *args, **kwargs):
        return self.obj.duration_count

    def resolve_duration_unit(self, info, *args, **kwargs):
        return self.obj.duration_unit

    def resolve_budget_currency(self, info, *args, **kwargs):
        return self.obj.budget_currency

    def resolve_budget_amount(self, info, *args, **kwargs):
        return self.obj.budget_amount

    def resolve_budget_unit(self, info, *args, **kwargs):
        return self.obj.budget_unit

    def resolve_budget_notes(self, info, *args, **kwargs):
        return self.obj.budget_notes

    def resolve_candidate_counts(self, info, *args, **kwargs):
        session = get_session()
        stages = session.query(StageModel).filter_by(template_id=1).all()
        session.close()
        counts = [CandidateCount(
            None, "All", len([c for c in self.obj.candidates if c.stage != "Remove from project"])
        )]
        for stg in stages:
            counts.append(CandidateCount(stg.id, stg.name, len([c for c in self.obj.candidates if c.stage == stg.name])))
        return counts

    def resolve_min_years_experience(self, info, *args, **kwargs):
        return self.obj.min_years_experience

    def resolve_max_years_experience(self, info, *args, **kwargs):
        return self.obj.max_years_experience

    def resolve_project_stage(self, info, *args, **kwargs):
        return "Matching" if not self.obj.project_status else self.obj.project_status

    def resolve_background(self, info, *args, **kwargs):
        background = self.obj.background.replace('"', '\"') if self.obj.background else ""
        return background

    def resolve_notes(self, info, *args, **kwargs):
        return self.obj.notes

    def resolve_project_type(self, info, *args, **kwargs):
        return self.obj.project_type

    def resolve_expertise(self, info, *args, **kwargs):
        session = get_session()
        attrs = self.obj.get_attributes(session, 'expertise')
        session.close()
        return [MasterProjectAttribute(attr) for attr in attrs]

    def resolve_sectors(self, info, *args, **kwargs):
        session = get_session()
        attrs = self.obj.get_attributes(session, 'sector')
        session.close()
        return [MasterProjectAttribute(attr) for attr in attrs]

    def resolve_scope_files(self, info):
        return [f.link for f in self.obj.scope_files]

    def resolve_scope_links(self, info):
        return [ScopeLink(f) for f in self.obj.scope_links]

    def resolve_members(self, info):
        return Admin.filtered_admins([f.member_id for f in self.obj.members])

    def resolve_note_list(self, info):
        def created_at(note):
            return note.created_at
        return [ProjectNote(n) for n in sorted(self.obj.note_list, key=created_at, reverse=True)]

    def resolve_directors(self, info):
        return Admin.filtered_admins([f.director_id for f in self.obj.directors])

    def resolve_stakeholders(self, info):
        return POC.from_ids(ids=[f.stakeholder_id for f in self.obj.stakeholders])

    def resolve_candidates(self, info, *args, **kwargs):
        start = kwargs.get('start', 0)
        end = kwargs.get('end', 9) + 1
        status = kwargs.get('status', "All")
        sort = kwargs.get('sort', None)
        candidates = self.obj.candidates
        if status != "All":
            candidates = [c for c in candidates if c.stage == status]
        candidates = [c for c in candidates if c.stage != "Remove from project"]
        cids = [c.id for c in candidates]
        session = get_session()
        candidates = session.query(ProjectCandidateMapModel).options(joinedload('freelancer')).filter(ProjectCandidateMapModel.id.in_(cids)).all()
        if sort:
            reverse = sort.startswith("-")
            sort = sort.replace("-", "")
            if sort == "alphabetical":
                candidates = sorted(candidates, key=lambda f: f.freelancer.name, reverse=reverse)
            if sort == "created":
                candidates = sorted(candidates, key=lambda f: f.freelancer.created_on, reverse=reverse)
            if sort == "modified":
                candidates = sorted(candidates, key=lambda f: f.freelancer.modified_at, reverse=reverse)
            if sort == "added_to_project":
                candidates = sorted(candidates, key=lambda f: f.added_on, reverse=reverse)

        return [ProjectCandidate(c, self.obj.id) for c in candidates[start:end]]

    def resolve_freelancer_location_type(self, info, *args, **kwargs):
        return self.obj.freelancer_location_type

    def resolve_educational_background(self, info, *args, **kwargs):
        return self.obj.educational_background

    def resolve_project_start_date(self, info, *args, **kwargs):
        return self.obj.project_start_date.strftime("%d %B %Y, %I:%M %p") if self.obj.project_start_date else ""

    def resolve_segment(self, info, *args, **kwargs):
        return self.obj.segment

    def resolve_sub_segment(self, info, *args, **kwargs):
        return self.obj.sub_segment

    def resolve_sharepoint_link(self, info, *args, **kwargs):
        return self.obj.sharepoint_link

    def resolve_is_client_confidential(self, info, *args, **kwargs):
        return self.obj.is_client_confidential

    @staticmethod
    def all(*args, **kwargs):
        from utils.index import search
        start = kwargs.get('start', 0)
        end = kwargs.get('end', 9) + 1
        session = get_session()
        if 'filter_stage' in kwargs:
            projects = session.query(MasterProjectModel).filter_by(project_status=kwargs['filter_stage']).all()
        else:
            # verify_admin(kwargs['token'])
            q = lower_plain_str(kwargs.get("q", ""))
            hits = search(q, "project", fields=['ac_search_field']).hits
            ids = [h.id for h in hits]
            projects = session.query(MasterProjectModel).filter(MasterProjectModel.id.in_(ids)).all()
            projects = sorted(projects, key=lambda p: p.created_at if p.created_at else datetime.datetime.min,
                              reverse=True)
        ans = [MasterProject(get_project_by_id(session, p.id)) for p in projects[start:end]]
        session.close()
        return ans

    @staticmethod
    def all_for_freelancer(*args, **kwargs):
        verify_admin(kwargs['token'])
        freelancer_id = kwargs['freelancer_id']
        session = get_session()
        project_ids = [c.project_id for c in get_candidates_for_freelancer(session, freelancer_id)]
        print(project_ids)
        projects = session.query(MasterProjectModel).all()
        session.close()
        return [MasterProject(p, p.id in project_ids) for p in projects]

    @staticmethod
    def detail(*args, **kwargs):
        verify_admin(kwargs['token'])
        project_id = kwargs['id']
        session = get_session()
        project = get_project_by_id(session, project_id)
        session.close()
        if not project:
            raise InvalidRequest("Project with id not found")
        return MasterProject(project, kwargs)


class MasterProjectWithCount(graphene.ObjectType):
    projects = graphene.List(MasterProject)
    count = graphene.Int()

    def all(*args, **kwargs):
        session = get_session()
        start = kwargs.get('start', 0)
        end = kwargs.get('end', 9) + 1

        if 'q' in kwargs and 'filter_stage' in kwargs:
            from utils.index import search
            q = lower_plain_str(kwargs.get("q", ""))
            hits = search(q, "project", fields=['ac_search_field']).hits
            ids = [h.id for h in hits]
            projects = session.query(MasterProjectModel).filter(MasterProjectModel.id.in_(ids)) \
                .filter_by(project_status=kwargs['filter_stage']).all()
            projects = sorted(projects, key=lambda p: p.created_at if p.created_at else datetime.datetime.min,
                              reverse=True)
        elif 'filter_stage' in kwargs:
            if 'filter_stage' in kwargs and 'admin_id' in kwargs:
                project_directors = session.query(ProjectDirectorsModel).filter_by(director_id=kwargs["admin_id"]).all()
                project_directors_ids = [pd.project_id for pd in project_directors]

                project_team_members = session.query(ProjectTeamMemberModel).filter_by(member_id=kwargs["admin_id"]).all()
                project_team_member_ids = [tm.project_id for tm in project_team_members]

                project_ids = list(set(project_directors_ids).union(set(project_team_member_ids)))

                projects = session.query(MasterProjectModel).filter(MasterProjectModel.id.in_(project_ids)).filter_by(project_status=kwargs['filter_stage']).all()
            else:
                projects = session.query(MasterProjectModel).filter_by(project_status=kwargs['filter_stage']).all()
            projects = sorted(projects, key=lambda p: p.created_at if p.created_at else datetime.datetime.min,
                              reverse=True)
        elif 'q' in kwargs:
            from utils.index import search
            q = lower_plain_str(kwargs.get("q", ""))
            hits = search(q, "project", fields=['ac_search_field']).hits
            ids = [h.id for h in hits]
            projects = session.query(MasterProjectModel).filter(MasterProjectModel.id.in_(ids)).all()
            projects = sorted(projects, key=lambda p: p.created_at if p.created_at else datetime.datetime.min,
                              reverse=True)
        else:
            projects = []

        count = len(projects)
        projects = [MasterProject(get_project_by_id(session, p.id)) for p in projects[start:end]]

        session.close()

        return MasterProjectWithCount(projects=projects, count=count)


class ResourcingConstants(graphene.ObjectType):
    segments = graphene.List(MasterProjectAttribute)
    sub_segments = graphene.List(MasterProjectAttribute)
    rating_criterias = graphene.List(MasterProjectAttribute)

    def resolve_segments(self, info, *args, **kwargs):
        session = get_session()
        segments = session.query(ProjectSegmentModel).all()
        session.close()
        return [MasterProjectAttribute(s) for s in segments]

    def resolve_sub_segments(self, info, *args, **kwargs):
        session = get_session()
        sub_segments = session.query(ProjectSubSegmentModel).all()
        session.close()
        return [MasterProjectAttribute(s) for s in sub_segments]

    def resolve_rating_criterias(self, info, *args, **kwargs):
        session = get_session()
        ratings = session.query(ProjectRatingCriteriaModel).all()
        session.close()
        return [MasterProjectAttribute(r) for r in ratings]

    @staticmethod
    def all(*args, **kwargs):
        verify_admin(kwargs['token'])
        return ResourcingConstants()


class ProjectFeedback(graphene.ObjectType):
    scales = graphene.List(Scale)
    criterias = graphene.List(ScaleCritera)

    def resolve_scales(self, info):
        session = get_session()
        required_scales = get_project_scales(session, self.project_id)
        for i in range(len(self.scales)):
            self.scales[i].obj.required = self.scales[i].obj.id in required_scales
        session.close()
        return self.scales

    def resolve_criterias(self, info):
        session = get_session()
        required_criterias = get_project_criterias(session, self.project_id)
        for i in range(len(self.criterias)):
            self.criterias[i].obj.required = self.criterias[i].obj.id in required_criterias
        session.close()
        return self.criterias

    def __init__(self, project_id, token):
        self.project_id = project_id
        self.scales = Scale.all(token=token)
        self.criterias = ScaleCritera.all_scale_criterias(token=token)

    @staticmethod
    def detail(*args, **kwargs):
        return ProjectFeedback(kwargs['project_id'], kwargs['token'])


class AdminDashboardCounts(graphene.ObjectType):
    pending_qa_count = graphene.Int()
    total_freelancers_count = graphene.Int()
    live_projects_count = graphene.Int()

    @staticmethod
    def all(*args, **kwargs):
        session = get_session()

        pending_qa = session.query(FreelancerModel).filter_by(interview_status="Pending").all()
        total_freelancers = session.query(FreelancerModel).all()
        live_projects = session.query(MasterProjectModel)\
            .filter(MasterProjectModel.project_status != "Won")\
            .filter(MasterProjectModel.project_status != "Lost").all()

        pending_qa_count = len(pending_qa)
        total_freelancers_count = len(total_freelancers)
        live_projects_count = len(live_projects)

        session.close()

        return AdminDashboardCounts(pending_qa_count=pending_qa_count,
                                    total_freelancers_count=total_freelancers_count,
                                    live_projects_count=live_projects_count)
