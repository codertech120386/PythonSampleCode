import graphene
import os
import datetime
from utils.decorators import update_project
from utils.authorization import verify_admin
from utils.exceptions import InvalidRequest
from utils.db import get_session
from utils.ses import send_template_email
from freelancer_profile.service import get_freelancer_email
from location.query import PlaceInput
from location.services import add_place
from .models import MasterProjectModel
from .serializers import index_project
from .query import MasterProject, ProjectFeedback, ProjectCandidate
from .services import (
    get_project_by_id, add_projection_location_details, add_project_resourcing, add_project_scope_link, add_project_scope_file, map_project_client,
    add_project_candidate, add_project_candidates, update_project_settings, get_candidates_with_id, reject_project_candidate, edit_project_candidate,
    set_project_criterias, set_project_scales, clear_project_scope_links, clear_project_scope_files,
    add_stakeholder, add_team_member, add_director, add_freelancer_note, add_project_note, clear_project_members,
    clear_project_directors, clear_project_stakeholders, update_candidate_quote, edit_freelancer_note, delete_freelancer_note,
    edit_project_note, delete_project_note
)
from utils.decorators import update_freelancer


class FileInput(graphene.InputObjectType):
    link = graphene.String()
    name = graphene.String()
    is_scope = graphene.Boolean()


class AddMasterProject(graphene.Mutation):
    class Arguments:
        token = graphene.String()
        name = graphene.String()
        background = graphene.String()
        project_type = graphene.String()
        notes = graphene.String()
        client_id = graphene.Int()
        no_of_freelancers = graphene.Int()
        expertise = graphene.List(graphene.String)
        stakeholder_ids = graphene.List(graphene.Int)
        sectors = graphene.List(graphene.String)
        duration_unit = graphene.String()
        duration_count = graphene.Int()
        budget_currency = graphene.String()
        budget_amount = graphene.Int()
        budget_unit = graphene.String()
        budget_notes = graphene.String()
        min_years_experience = graphene.Int()
        max_years_experience = graphene.Int()
        member_ids = graphene.List(graphene.Int)
        director_ids = graphene.List(graphene.Int)
        scope_files = graphene.List(graphene.String)
        scope_links = graphene.List(FileInput)
        id = graphene.Int(required=False)
        project_status = graphene.String(required=False)
        location = graphene.Argument(PlaceInput, required=False)
        freelancer_location_type = graphene.String()
        educational_background = graphene.String()
        project_start_date = graphene.Date(required=False)
        segment = graphene.String(required=True)
        sub_segment = graphene.String(required=False)
        is_client_confidential = graphene.Boolean(required=False)
        sharepoint_link = graphene.String(required=False)
        client_type = graphene.String(required=False)
        closed_quarter = graphene.String(required=False)
        closed_year = graphene.String(required=False)

    project = graphene.Field(MasterProject)

    def mutate(self, info, *args, **kwargs):
        token = kwargs.pop('token')
        if kwargs.get('project_type', "") == 'freelance' and not kwargs.get('no_of_freelancers', None):
            raise InvalidRequest("Number of freelancers not provided")
        if 'min_years_experience' in kwargs and 'max_years_experience' in kwargs:
            if kwargs['min_years_experience'] >= kwargs['max_years_experience']:
                raise InvalidRequest("Max experience required should be greater than min experience")

        expertise = kwargs.pop('expertise', [])
        if expertise == "":
            expertise = []
        sectors = kwargs.pop('sectors', [])
        if sectors == "":
            sectors = []
        stakeholders = kwargs.pop('stakeholder_ids', [])
        member_ids = kwargs.pop('member_ids', [])
        director_ids = kwargs.pop('director_ids', [])
        scope_files = kwargs.pop('scope_files', [])
        scope_links = kwargs.pop('scope_links', [])
        location = kwargs.pop('location', None)
        user = verify_admin(token)
        session = get_session()

        # if len(scope_files) == 0 and len(scope_links) == 0:
        #     raise InvalidRequest("A project scope link or file is required")
        if 'id' in kwargs:
            project = get_project_by_id(session, kwargs['id'])
            project.modified_at = datetime.datetime.utcnow()

            if 'project_start_date' in kwargs:
                project.project_start_date = kwargs.pop('project_start_date')
            for key in kwargs:
                setattr(project, key, kwargs[key])
            if 'expertise' in kwargs:
                project.update_attributes(session, 'expertise', expertise)
            if 'sector' in kwargs:
                project.update_attributes(session, 'sector', sectors)
        else:
            project = MasterProjectModel(**kwargs)
            project.admin_id = user.id
            project.modified_at = datetime.datetime.utcnow()

            if 'project_start_date' in kwargs:
                project.project_start_date = kwargs.pop('project_start_date')
            session.add(project)
            session.flush()
            project.update_attributes(session, 'expertise', expertise)
            project.update_attributes(session, 'sector', sectors)

        clear_project_scope_files(session, project.id)
        clear_project_scope_links(session, project.id)
        clear_project_stakeholders(session, project.id)
        clear_project_members(session, project.id)
        clear_project_directors(session, project.id)
        for f in scope_files:
            add_project_scope_file(session, project.id, f)
        for f in scope_links:
            add_project_scope_link(session, project.id, f['name'], f['link'], f['is_scope'])
        for s in stakeholders:
            add_stakeholder(session, project.id, s)
        for t in member_ids:
            add_team_member(session, project.id, t)
        for d in director_ids:
            add_director(session, project.id, d)

        project.project_status = kwargs['project_status'] if 'project_status' in kwargs else "Market Scan"

        if location:
            project.location_id = add_place(session, location)
            project.city = location.city
            project.country = location.country
        project = get_project_by_id(session, project.id)
        session.commit()
        index_project(project.id)
        return AddMasterProject(project=MasterProject(project))


class AddMasterProjectLocation(graphene.Mutation):
    class Arguments:
        token = graphene.String()
        project_id = graphene.Int()
        location = graphene.String()
        location_type = graphene.String()
        looking_for = graphene.String()
        start_date = graphene.Date()
        duration_count = graphene.Int()
        duration_unit = graphene.String()
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

    master_project = graphene.Field(MasterProject)

    def mutate(self, info, *args, **kwargs):
        verify_admin(kwargs['token'])
        session = get_session()
        print("called mutate")
        project = get_project_by_id(session, kwargs['project_id'])
        if not project:
            raise InvalidRequest("Project not found")
        add_projection_location_details(session, project, **kwargs)
        session.commit()
        session.refresh(project)
        session.close()
        return AddMasterProjectLocation(master_project=MasterProject(project))


class AddMasterProjectResourcing(graphene.Mutation):
    class Arguments:
        token = graphene.String()
        project_id = graphene.Int()
        segment_id = graphene.Int()
        sub_segment_id = graphene.Int()
        rating_criteria_id = graphene.Int()
        director_id = graphene.Int()
        lead_id = graphene.Int()
        member_ids = graphene.List(graphene.Int)
        notes = graphene.String()

    master_project = graphene.Field(MasterProject)

    def mutate(self, info, *args, **kwargs):
        verify_admin(kwargs['token'])
        session = get_session()
        project = get_project_by_id(session, kwargs['project_id'])
        if not project:
            raise InvalidRequest("Project not found")
        add_project_resourcing(session, **kwargs)
        session.commit()
        session.refresh(project)
        session.close()
        return AddMasterProjectLocation(master_project=MasterProject(project))


class DocInput(graphene.InputObjectType):
    link = graphene.String()
    # will parse the string to time in the validate method for the slot model
    document_name = graphene.String()
    is_scope = graphene.Boolean()


class AddMasterProjectScopeLink(graphene.Mutation):
    class Arguments:
        token = graphene.String()
        project_id = graphene.Int()
        docs = graphene.List(DocInput)

    master_project = graphene.Field(MasterProject)

    def mutate(self, info, token, project_id, docs):
        verify_admin(token)
        session = get_session()
        project = get_project_by_id(session, project_id)
        if not project:
            raise InvalidRequest("Project not found")
        clear_project_scope_links(session, project_id)
        for doc in docs:
            add_project_scope_link(session, project_id, doc['document_name'], doc['link'], doc['is_scope'])
        session.commit()
        session.refresh(project)
        session.close()
        return AddMasterProjectLocation(master_project=MasterProject.detail(token=token, id=project_id))


class AddMasterProjectScopeFiles(graphene.Mutation):
    class Arguments:
        token = graphene.String()
        links = graphene.List(FileInput)
        project_id = graphene.Int()

    master_project = graphene.Field(MasterProject)

    def mutate(self, info, token, project_id, links):
        verify_admin(token)
        session = get_session()
        project = get_project_by_id(session, project_id)
        if not project:
            raise InvalidRequest("Project not found")
        clear_project_scope_files(session, project_id)
        for link in links:
            add_project_scope_file(session, project_id, link)
        session.commit()
        session.refresh(project)
        session.close()
        return AddMasterProjectLocation(master_project=MasterProject.detail(token=token, id=project_id))


class AddMasterProjectClient(graphene.Mutation):
    class Arguments:
        token = graphene.String()
        project_id = graphene.Int()
        client_id = graphene.Int()
        stakeholder_id = graphene.Int()

    master_project = graphene.Field(MasterProject)

    def mutate(self, info, token, project_id, client_id, stakeholder_id):
        verify_admin(token)
        session = get_session()
        project = get_project_by_id(session, project_id)
        if not project:
            raise InvalidRequest("Project not found")
        map_project_client(session, project_id, client_id, stakeholder_id)
        session.commit()
        session.refresh(project)
        session.close()
        return AddMasterProjectClient(master_project=MasterProject(project))


class AddMasterProjectCandidate(graphene.Mutation):
    class Arguments:
        token = graphene.String()
        project_ids = graphene.List(graphene.Int)
        freelancer_id = graphene.Int()

    candidates = graphene.List(ProjectCandidate)

    def mutate(self, info, token, project_ids, freelancer_id):
        verify_admin(token)
        session = get_session()
        for project_id in project_ids:
            project = get_project_by_id(session, project_id)
            if not project:
                raise InvalidRequest("Project id {} not found".format(project_id))
        add_project_candidates(session, project_ids, freelancer_id)
        session.commit()
        projects = ProjectCandidate.freelancer_projects(token=token, freelancer_id=freelancer_id)
        session.close()
        return AddMasterProjectCandidate(candidates=[p for p in projects if p.obj.project_id in project_ids])


class EditMasterProjectSettings(graphene.Mutation):
    class Arguments:
        token = graphene.String()
        project_id = graphene.Int()
        hiring_stage_id = graphene.Int()

    master_project = graphene.Field(MasterProject)

    def mutate(self, info, token, project_id, hiring_stage_id):
        verify_admin(token)
        session = get_session()
        project = get_project_by_id(session, project_id)
        if not project:
            raise InvalidRequest("Project not found")
        update_project_settings(session, project_id, hiring_stage_id)
        session.commit()
        session.refresh(project)
        session.close()
        return EditMasterProjectSettings(master_project=MasterProject(project))


class EditMasterProjectStage(graphene.Mutation):
    class Arguments:
        token = graphene.String()
        project_id = graphene.Int()
        stage = graphene.String()

    master_project = graphene.Field(MasterProject)

    @update_project
    def mutate(self, info, token, project_id, stage):
        allowed_stage_values = [
            "Market Scan",
            "Selection",
            "Matching",
            "Contracting",
            "Won",
            "Lost"
        ]
        verify_admin(token)
        if stage not in allowed_stage_values:
            raise InvalidRequest("Invalid stage value, allowed values are - " + str(allowed_stage_values))
        session = get_session()
        project = get_project_by_id(session, project_id)
        if not project:
            raise InvalidRequest("Project not found")
        project.project_status = stage
        session.commit()
        session.close()
        return EditMasterProjectSettings(master_project=MasterProject.detail(token=token, id=project_id))


class SendBulkEmail(graphene.Mutation):
    class Arguments:
        token = graphene.String()
        subject = graphene.String()
        body = graphene.String()
        candidates = graphene.List(graphene.Int)

    message = graphene.String()

    def mutate(self, info, token, subject, body, candidates):
        session = get_session()
        candidates = get_candidates_with_id(session, candidates)
        emails = [get_freelancer_email(session, c.freelancer_id) for c in candidates]
        for email in emails:
            send_template_email(email, subject, body)
        session.close()
        return SendBulkEmail(message="Bulk email sent")


class RejectMasterProjectCandidates(graphene.Mutation):
    class Arguments:
        token = graphene.String()
        candidate_ids = graphene.List(graphene.Int)
        project_id = graphene.Int()

    master_project = graphene.Field(MasterProject)

    def mutate(self, info, token, project_id, candidate_ids):
        verify_admin(token)
        session = get_session()
        reject_project_candidate(session, candidate_ids)
        session.commit()
        session.close()
        return RejectMasterProjectCandidates(master_project=MasterProject.detail(token=token, id=project_id))


class EditMasterProjectCandidate(graphene.Mutation):
    class Arguments:
        token = graphene.String()
        candidate_id = graphene.List(graphene.Int)
        project_id = graphene.Int()
        status = graphene.String(required=False)
        rate_currency = graphene.String(required=False)
        rate_amount = graphene.Int(required=False)
        rate_unit = graphene.String(required=False)

    master_project = graphene.Field(MasterProject)

    @update_project
    def mutate(self, info, token, project_id, candidate_id, **kwargs):
        verify_admin(token)
        session = get_session()
        print(candidate_id)
        kwargs['stage'] = kwargs.pop('status', None)
        edit_project_candidate(session, candidate_id, **kwargs)
        session.commit()
        session.close()
        return EditMasterProjectCandidate(master_project=MasterProject.detail(token=token, id=project_id))


class EditMasterProjectFeedback(graphene.Mutation):
    class Arguments:
        token = graphene.String()
        project_id = graphene.Int()
        scale_ids = graphene.List(graphene.Int)
        criteria_ids = graphene.List(graphene.Int)

    feedback_form = graphene.Field(ProjectFeedback)

    def mutate(self, info, token, project_id, scale_ids, criteria_ids):
        verify_admin(token)
        session = get_session()
        project = get_project_by_id(session, project_id)
        if not project:
            raise InvalidRequest("Project not found")
        set_project_criterias(session, project_id, criteria_ids)
        set_project_scales(session, project_id, scale_ids)
        session.commit()
        session.close()
        return EditMasterProjectFeedback(feedback_form=ProjectFeedback(project_id=project_id, token=token))


class AddFreelancerNote(graphene.Mutation):
    class Arguments:
        token = graphene.String()
        note = graphene.String()
        freelancer_id = graphene.Int()
        project_id = graphene.Int(required=False)

    message = graphene.String()

    @update_freelancer
    def mutate(self, info, token, note, freelancer_id, **kwargs):
        admin = verify_admin(token)
        session = get_session()
        add_freelancer_note(session, freelancer_id, admin.id, note, kwargs.get('project_id', None))
        session.commit()
        session.close()
        return AddFreelancerNote(message="added note for freelancer")


class EditFreelancerNote(graphene.Mutation):
    class Arguments:
        token = graphene.String()
        note_id = graphene.Int()
        note = graphene.String()

    message = graphene.String()

    def mutate(self, info, token, note_id, note, **kwargs):
        admin = verify_admin(token)
        session = get_session()
        edit_freelancer_note(session, admin.id, note_id, note)
        session.commit()
        session.close()
        return AddFreelancerNote(message="added note for freelancer")


class DeleteFreelancerNote(graphene.Mutation):
    class Arguments:
        token = graphene.String()
        note_id = graphene.Int()

    message = graphene.String()

    def mutate(self, info, token, note_id, **kwargs):
        admin = verify_admin(token)
        session = get_session()
        delete_freelancer_note(session, admin.id, note_id)
        session.commit()
        session.close()
        return AddFreelancerNote(message="added note for freelancer")


class AddProjectNote(graphene.Mutation):
    class Arguments:
        token = graphene.String()
        note = graphene.String()
        project_id = graphene.Int()

    message = graphene.String()

    @update_project
    def mutate(self, info, token, note, project_id):
        admin = verify_admin(token)
        session = get_session()
        add_project_note(session, admin.id, note, project_id)
        session.commit()
        session.close()
        return AddProjectNote(message="added note for project")


class EditProjectNote(graphene.Mutation):

    class Arguments:
        token = graphene.String()
        note = graphene.String()
        note_id = graphene.Int()

    message = graphene.String()

    @update_project
    def mutate(self, info, token, note, note_id):
        admin = verify_admin(token)
        session = get_session()
        edit_project_note(session, admin.id, note_id, note)
        session.commit()
        session.close()
        return AddProjectNote(message="edited note for project")


class DeleteProjectNote(graphene.Mutation):
    class Arguments:
        token = graphene.String()
        note_id = graphene.Int()

    message = graphene.String()

    @update_project
    def mutate(self, info, token, note_id):
        admin = verify_admin(token)
        session = get_session()
        delete_project_note(session, admin.id, note_id)
        session.commit()
        session.close()
        return AddProjectNote(message="deleted note for project")


class DeleteProject(graphene.Mutation):
    class Arguments:
        token = graphene.String()
        project_id = graphene.Int()

    message = graphene.String()

    @update_project
    def mutate(self, info, token, project_id):
        from freelancer_new.services import delete_project
        admin = verify_admin(token)
        session = get_session()
        delete_project(session,project_id)
        session.commit()
        session.close()
        return DeleteProject(message="deleted the project")


class DeleteFreelancer(graphene.Mutation):
    class Arguments:
        token = graphene.String()
        freelancer_id = graphene.Int()

    message = graphene.String()

    @update_project
    def mutate(self, info, token, freelancer_id):
        from freelancer_new.services import delete_freelancer
        admin = verify_admin(token)
        session = get_session()
        delete_freelancer(session, freelancer_id)
        session.commit()
        session.close()
        return DeleteFreelancer(message="deleted the freelancer")


class EditCandidateQuote(graphene.Mutation):
    class Arguments:
        token = graphene.String()
        project_id = graphene.Int()
        freelancer_id = graphene.Int()
        rate_unit = graphene.String()
        rate_currency = graphene.String()
        rate_amount = graphene.Int()

    projects = graphene.List(ProjectCandidate)

    @update_project
    def mutate(self, info, token, project_id, freelancer_id, **kwargs):
        verify_admin(token)
        session = get_session()
        update_candidate_quote(session, project_id, freelancer_id, **kwargs)
        session.commit()
        session.close()
        return EditCandidateQuote(projects=ProjectCandidate.freelancer_projects(token=token, freelancer_id=freelancer_id))
