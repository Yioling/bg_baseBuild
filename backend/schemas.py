"""Pydantic 请求/响应模型。"""
from pydantic import BaseModel
from typing import Optional


# ---------- 认证 ----------
class LoginReq(BaseModel):
    username: str
    password: str

class RegisterReq(BaseModel):
    username: str
    password: str
    role: str  # master | apprentice
    company_id: int | None = None
    master_id: int | None = None  # 徒弟注册时选择的师傅
    employee_no: str | None = None  # 工号
    phone: str | None = None  # 手机号
    office_account: str | None = None  # 办公软件账号
    full_name: str | None = None  # 姓名

class CreateApprenticeReq(BaseModel):
    username: str
    password: str

class CompanyPostReq(BaseModel):
    content: str

class AssignMasterReq(BaseModel):
    apprentice_id: int
    master_id: int

# ---------- 资料投喂 ----------
class IngestPathReq(BaseModel):
    path: str

class IngestUrlReq(BaseModel):
    urls: list[str]

# ---------- 计划 ----------
class PlanGenerateReq(BaseModel):
    apprentice_id: int

class PlanTaskUpdate(BaseModel):
    title: Optional[str] = None
    task_type: Optional[str] = None
    duration_min: Optional[int] = None
    sort_order: Optional[int] = None

class PlanDayUpdate(BaseModel):
    note: Optional[str] = None
    locked: Optional[int] = None

# ---------- 测评 ----------
class AssessmentAnswerReq(BaseModel):
    question_id: int
    answer: str

# ---------- 陪练 ----------
class ChatReq(BaseModel):
    question: str

# ---------- PDF ----------
class PDFGenReq(BaseModel):
    plan_day_id: Optional[int] = None

# ---------- V2 课程 ----------
class CourseReq(BaseModel):
    title: str
    type: str = "document"
    content: str = ""

# ---------- V2 计划 ----------
class PlanCreateReq(BaseModel):
    apprentice_id: int
    name: str = "培养计划"
    course_ids: list[int] = []

# ---------- V2 Quiz ----------
class QuizSubmitReq(BaseModel):
    plan_item_id: int
    answer: str

class QuizScoreReq(BaseModel):
    master_score: float
    status: str = "passed"

# ---------- V2 进度 ----------
class DailyProgressReq(BaseModel):
    apprentice_id: int
    plan_item_id: Optional[int] = None

# ---------- V2 帖子 ----------
class PostReq(BaseModel):
    content: str
    author_name: Optional[str] = None

class CommentReq(BaseModel):
    content: str

# ---------- V2 管理 ----------
class ApproveReq(BaseModel):
    user_id: int

class RebindReq(BaseModel):
    apprentice_id: int
    master_id: int

class DepartmentReq(BaseModel):
    name: str
