import datetime
from utils.db import Base
from sqlalchemy import ForeignKey, Column, Integer, Text, Boolean, String, Date, DateTime
from sqlalchemy.orm import relationship, validates
from utils.exceptions import InvalidRequest
from freelancer_auth.models import FreelancerModel
from freelancer_profile.models import Skill, Sector
from freelancer_portfolio.models import FileMixin
from auth.models import UserModel
from process.models import TemplateModel
from scales.models import ScaleModel, ScaleCriteraModel
from clients.models import ClientPOCModel, ClientMasterModel


PROJECT_TYPES = ['freelance', 'firm', 'rfp']
DURATION_UNITS = ['days', 'weeks', 'months', 'years']
BUDGET_UNIT = ['hour', 'day', 'week', 'month', 'year', 'project']


class MasterProjectModel(Base):
    __tablename__ = "master_projects"
    id = Column(Integer, primary_key=True)
    no_of_freelancers = Column(Integer)
    name = Column(String(255))
    project_type = Column(String(255))
    background = Column(Text)
    notes = Column(Text)
    client_id = Column(Integer, ForeignKey(ClientMasterModel.id))
    location_id = Column(String)
    duration_unit = Column(String(255))
    duration_count = Column(Integer)
    budget_currency = Column(String(255))
    budget_amount = Column(Integer)
    budget_unit = Column(String(255))
    budget_notes = Column(Text)
    project_status = Column(String(255))
    admin_id = Column(Integer)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    modified_at = Column(DateTime)
    min_years_experience = Column(Integer)
    max_years_experience = Column(Integer)
    stakeholders = relationship("ProjectStakeholdersModel", back_populates="project")
    candidates = relationship("ProjectCandidateMapModel", back_populates="project")
    members = relationship("ProjectTeamMemberModel", back_populates="project")
    directors = relationship("ProjectDirectorsModel", back_populates="project")
    scope_files = relationship("ProjectScopeFileModel", back_populates="project")
    scope_links = relationship("ProjectScopeLinkModel", back_populates="project")
    note_list = relationship("ProjectNoteModel", back_populates="project")
    freelancer_location_type = Column(String(50))
    educational_background = Column(Text)
    project_start_date = Column(Date, nullable=True)
    segment = Column(String(50))
    sub_segment = Column(String(255))
    is_client_confidential = Column(Boolean, default=False)
    sharepoint_link = Column(String(1000))
    city = Column(String(255), nullable=True)
    country = Column(String(255), nullable=True)
    client_type = Column(String(255), nullable=True)
    closed_quarter = Column(String(255), nullable=True)
    closed_year = Column(String(4), nullable=True)

    def update_attributes(self, session, map_name, map_values):
        print(map_name, map_values)
        if map_name not in MasterProjectAttributeMap.MAP:
            raise InvalidRequest("attribute type {} not supported".format(map_name))
        table = MasterProjectAttributeMap.MAP[map_name]

        session.query(MasterProjectAttributeMap).filter_by(map_name=map_name, project_id=self.id).delete()
        for value in map_values:
            map_objs = session.query(table).filter_by(name=value).all()
            if not map_objs:
                map_obj = table(name=value)
                print(table, value, map_obj)
                session.add(map_obj)
                session.flush()
            else:
                map_obj = map_objs[0]
            a = MasterProjectAttributeMap(map_name=map_name, map_id=map_obj.id, project_id=self.id)
            session.add(a)
        session.flush()

    def get_attributes(self, session, map_name):
        if map_name not in MasterProjectAttributeMap.MAP:
            raise InvalidRequest("attribute type {} not supported".format(map_name))
        table = MasterProjectAttributeMap.MAP[map_name]

        map_ids = [m.map_id for m in session.query(MasterProjectAttributeMap).filter_by(map_name=map_name, project_id=self.id).all()]
        return session.query(table).filter(table.id.in_(map_ids)).all()

    @validates('location_id')
    def validate_location_id(self, key, location_id):
        from location.services import get_place
        from utils.db import get_session
        session = get_session()
        if location_id:
            try:
                place = get_place(session, self.location_id)
                self.city = place.city
                self.country = place.country
            except:
                pass
        return location_id


class ProjectStakeholdersModel(Base):
    __tablename__ = 'project_stakeholders'
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey(MasterProjectModel.id))
    project = relationship(MasterProjectModel)
    stakeholder_id = Column(Integer, ForeignKey(ClientPOCModel.id))
    stakeholder = relationship(MasterProjectModel)


class MasterProjectAttributeMap(Base):
    MAP = {
        "sector": Sector,
        "expertise": Skill
    }
    __tablename__ = 'master_project_attribute_map'

    id = Column(Integer, primary_key=True)
    map_name = Column(String(100))
    project_id = Column(Integer, ForeignKey(MasterProjectModel.id))
    project = relationship(MasterProjectModel)
    map_id = Column(Integer)


class ProjectLocationModel(Base):
    __tablename__ = 'project_location_details'
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey(MasterProjectModel.id))
    project = relationship(MasterProjectModel)
    location = Column(String(200))
    looking_for = Column(String(200))
    duration_count = Column(Integer)
    duration_unit = Column(String(20))
    location_type = Column(String(50))
    start_date = Column(Date)
    budget_currency = Column(String(10))
    budget_amount = Column(Integer)
    enable_full_time = Column(Boolean, default=False)
    expected_annual_salary = Column(Integer, nullable=True)
    enable_fixed_rate_projects = Column(Boolean, default=False)
    expected_monthly_rate = Column(Integer, nullable=True)
    enable_full_day_projects = Column(Boolean, default=False)
    expected_daily_rate = Column(Integer, nullable=True)
    enable_hourly_projects = Column(Boolean, default=False)
    expected_hourly_rate = Column(Integer, nullable=True)
    min_hours = Column(Integer, nullable=True)


class ProjectSegmentModel(Base):
    __tablename__ = 'project_segments'
    id = Column(Integer, primary_key=True)
    name = Column(String(255))


class ProjectSubSegmentModel(Base):
    __tablename__ = 'project_sub_segments'
    id = Column(Integer, primary_key=True)
    name = Column(String(255))


class ProjectRatingCriteriaModel(Base):
    __tablename__ = 'project_rating_criteria'
    id = Column(Integer, primary_key=True)
    name = Column(String(255))


class ProjectResourcingModel(Base):
    __tablename__ = "project_resourcings"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey(MasterProjectModel.id))
    project = relationship(MasterProjectModel)
    segment_id = Column(Integer, ForeignKey(ProjectSegmentModel.id))
    segment = relationship(ProjectSegmentModel)
    rating_criteria_id = Column(Integer, ForeignKey(ProjectRatingCriteriaModel.id))
    rating_criteria = relationship(ProjectRatingCriteriaModel)
    sub_segment_id = Column(Integer, ForeignKey(ProjectSubSegmentModel.id))
    sub_segment = relationship(ProjectSubSegmentModel)
    director_id = Column(Integer, ForeignKey(UserModel.id))
    director = relationship(UserModel, foreign_keys=[director_id])
    lead_id = Column(Integer, ForeignKey(UserModel.id))
    lead = relationship(UserModel, foreign_keys=[lead_id])
    notes = Column(Text)


class ProjectTeamMemberModel(Base):
    __tablename__ = "project_team_members"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey(MasterProjectModel.id))
    project = relationship(MasterProjectModel)
    member_id = Column(Integer, ForeignKey(UserModel.id))
    member = relationship(UserModel)


class ProjectDirectorsModel(Base):
    __tablename__ = "project_directors"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey(MasterProjectModel.id))
    project = relationship(MasterProjectModel)
    director_id = Column(Integer, ForeignKey(UserModel.id))
    director = relationship(UserModel)


class ProjectScopeLinkModel(Base):
    __tablename__ = "project_scope_links"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey(MasterProjectModel.id))
    project = relationship(MasterProjectModel)
    document_name = Column(String(255))
    link = Column(Text)
    is_scope = Column(Boolean, default=False)


class ProjectScopeFileModel(Base):
    __tablename__ = "project_scope_files"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey(MasterProjectModel.id))
    project = relationship(MasterProjectModel)
    name = Column(String(255))
    link = Column(Text)
    is_scope = Column(Boolean, default=False)


class ProjectClientModel(Base):
    __tablename__ = "project_client_map"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey(MasterProjectModel.id))
    project = relationship(MasterProjectModel)
    client_id = Column(Integer, ForeignKey(ClientMasterModel.id))
    client = relationship(ClientMasterModel)
    stakeholder_id = Column(Integer, ForeignKey(ClientPOCModel.id))
    stakeholder = relationship(ClientPOCModel)


class ProjectCandidateMapModel(Base):
    __tablename__ = "project_candidate_map"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey(MasterProjectModel.id))
    project = relationship(MasterProjectModel)
    rejected = Column(Boolean, default=False)
    freelancer_id = Column(Integer, ForeignKey(FreelancerModel.id))
    freelancer = relationship(FreelancerModel)
    added_on = Column(DateTime, default=datetime.datetime.utcnow)
    stage = Column(String(255))
    rate_unit = Column(String(255))
    rate_currency = Column(String(255))
    rate_amount = Column(Integer)


class ProjectScaleMapModel(Base):
    __tablename__ = "project_scale_map"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey(MasterProjectModel.id))
    project = relationship(MasterProjectModel)
    scale_id = Column(Integer, ForeignKey(ScaleModel.id))
    scale = relationship(ScaleModel)


class ProjectCriteriaMapModel(Base):
    __tablename__ = "project_criteria_map"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey(MasterProjectModel.id))
    project = relationship(MasterProjectModel)
    criteria_id = Column(Integer, ForeignKey(ScaleCriteraModel.id))
    criteria = relationship(ScaleCriteraModel)


class ProjectNoteModel(Base):
    __tablename__ = 'project_notes'

    id = Column(Integer, primary_key=True)
    note = Column(Text)
    project_id = Column(Integer, ForeignKey(MasterProjectModel.id))
    project = relationship(MasterProjectModel)
    admin_id = Column(Integer, ForeignKey(UserModel.id))
    admin = relationship(UserModel)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
