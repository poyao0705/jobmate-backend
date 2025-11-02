from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

from flask import jsonify, request
from sqlalchemy.orm import joinedload

from jobmate_agent.extensions import db
from jobmate_agent.jwt_auth import require_jwt
from jobmate_agent.models import Goal, LearningItem, Task

from jobmate_agent.blueprints.api import api_bp
from .chat import _ensure_user_from_profile


PRIORITY_LEVELS = {
    "high": 3,
    "medium": 2,
    "low": 1,
    "optional": 0,
}
DEFAULT_PRIORITY_KEY = "medium"
PRIORITY_LOOKUP = {value: key for key, value in PRIORITY_LEVELS.items()}


# ======== 工具函数区域 ========
def _parse_iso_date(value: Optional[str]) -> Optional[date]:
    """将 ISO 字符串解析为 date；遇到空值/非法格式时返回 None。"""
    if value in (None, "", "null"):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _task_matches_date(task: Task, target: date) -> bool:
    """判断任务在给定日期内是否活跃，用于前端日历/过滤。"""
    if task.start_date and task.end_date:
        return task.start_date <= target <= task.end_date
    if task.start_date:
        return task.start_date == target
    if task.end_date:
        return task.end_date == target
    return True


def _serialize_goal(goal: Goal) -> Dict[str, Any]:
    """把 Goal 模型格式化为前端可用的 JSON。"""
    return {
        "id": goal.id,
        "title": goal.title,
        "description": goal.description or "",
        "created_at": goal.created_at.isoformat() if goal.created_at else None,
    }


def _serialize_task(task: Task) -> Dict[str, Any]:
    """把 Task 连同 notes/learning_item/goal 一并序列化。"""
    learning_item: Optional[LearningItem] = getattr(task, "learning_item", None)
    goal: Optional[Goal] = task.goal
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description or "",
        "start_date": task.start_date.isoformat() if task.start_date else None,
        "end_date": task.end_date.isoformat() if task.end_date else None,
        "done": task.done,
        "priority": PRIORITY_LOOKUP.get(task.priority, DEFAULT_PRIORITY_KEY),
        "goal": _serialize_goal(goal) if goal else None,
        "learning_item": {
            "id": learning_item.id,
            "title": learning_item.title,
            "url": learning_item.url,
            "source": learning_item.source,
        }
        if learning_item
        else None,
        "notes": [
            {
                "id": note.id,
                "content": note.content or "",
                "created_at": note.created_at.isoformat()
                if note.created_at
                else None,
            }
            for note in task.notes
        ],
        "created_at": task.created_at.isoformat() if task.created_at else None,
    }


def _normalize_priority(value: Any) -> Optional[int]:
    """把传入的优先级字符串/数字转换成内部整数等级。"""
    if value is None:
        return PRIORITY_LEVELS[DEFAULT_PRIORITY_KEY]

    if isinstance(value, str):
        normalized = value.strip().lower()
        if not normalized:
            return PRIORITY_LEVELS[DEFAULT_PRIORITY_KEY]
        if normalized not in PRIORITY_LEVELS:
            return None
        return PRIORITY_LEVELS[normalized]

    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return None

    if numeric in PRIORITY_LOOKUP:
        return numeric

    if numeric < min(PRIORITY_LOOKUP):
        return PRIORITY_LEVELS["optional"]
    if numeric > max(PRIORITY_LOOKUP):
        return PRIORITY_LEVELS["high"]

    return PRIORITY_LEVELS[DEFAULT_PRIORITY_KEY]


def _enforce_user():
    """确保 Auth0 Profile 映射到本地 User，没有则抛 404。"""
    user = _ensure_user_from_profile()
    if user is None:
        return None, jsonify({"error": "User profile not found"}), 404
    return user, None, None


# ======== 任务增删改查接口 ========
@api_bp.route("/tasks", methods=["GET"])
@require_jwt(hydrate=True)
def list_tasks():
    """任务列表：支持 goal/date 筛选，并返回备选目标列表。"""
    user, error_response, status = _enforce_user()
    if error_response:
        return error_response, status

    query = (
        Task.query.options(
            joinedload(Task.notes),
            joinedload(Task.learning_item),
            joinedload(Task.goal),
        )
        .filter_by(user_id=user.id)
        .order_by(Task.start_date.asc(), Task.created_at.asc())
    )

    goal_id = request.args.get("goal_id", type=int)
    if goal_id:
        query = query.filter_by(goal_id=goal_id)

    tasks = query.all()

    filter_date_raw = request.args.get("date")
    if filter_date_raw:
        filter_date = _parse_iso_date(filter_date_raw)
        if filter_date is None:
            return (
                jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}),
                400,
        )
        tasks = [task for task in tasks if _task_matches_date(task, filter_date)]

    goals = (
        Goal.query.filter_by(user_id=user.id)
        .order_by(Goal.created_at.desc())
        .all()
    )

    return jsonify(
        {
            "tasks": [_serialize_task(task) for task in tasks],
            "goals": [_serialize_goal(goal) for goal in goals],
        }
    )


@api_bp.route("/tasks", methods=["POST"])
@require_jwt(hydrate=True)
def create_task():
    """创建任务：至少传 title，可选描述/日期/优先级/关联指标。"""
    user, error_response, status = _enforce_user()
    if error_response:
        return error_response, status

    payload = request.get_json(silent=True) or {}
    title = (payload.get("title") or "").strip()
    if not title:
        return jsonify({"error": "Title is required."}), 400

    description = (payload.get("description") or "").strip() or None
    start_date = _parse_iso_date(payload.get("start_date"))
    end_date = _parse_iso_date(payload.get("end_date"))
    done = bool(payload.get("done", False))
    priority_value = _normalize_priority(payload.get("priority"))
    if priority_value is None:
        valid_options = ", ".join(PRIORITY_LEVELS.keys())
        return (
            jsonify({"error": f"Priority must be one of: {valid_options}."}),
            400,
        )

    goal_id = payload.get("goal_id")
    goal = None
    if goal_id is not None:
        goal = Goal.query.filter_by(id=goal_id, user_id=user.id).first()
        if goal is None:
            return jsonify({"error": "Goal not found for current user."}), 404

    learning_item_id = payload.get("learning_item_id")
    learning_item = None
    if learning_item_id is not None:
        learning_item = LearningItem.query.get(learning_item_id)
        if learning_item is None:
            return jsonify({"error": "Learning item not found."}), 404

    task = Task(
        user_id=user.id,
        title=title,
        description=description,
        start_date=start_date,
        end_date=end_date,
        done=done,
        priority=priority_value,
        goal_id=goal.id if goal else None,
        learning_item_id=learning_item.id if learning_item else None,
    )
    db.session.add(task)
    db.session.commit()

    task = (
        Task.query.options(
            joinedload(Task.notes),
            joinedload(Task.learning_item),
            joinedload(Task.goal),
        )
        .filter_by(id=task.id, user_id=user.id)
        .first()
    )
    return jsonify({"task": _serialize_task(task)}), 201


@api_bp.route("/tasks/<int:task_id>", methods=["PATCH"])
@require_jwt(hydrate=True)
def update_task(task_id: int):
    """更新任务：支持标题、描述、日期、状态、优先级、目标、学习项。"""
    user, error_response, status = _enforce_user()
    if error_response:
        return error_response, status

    task = (
        Task.query.options(
            joinedload(Task.notes),
            joinedload(Task.learning_item),
            joinedload(Task.goal),
        )
        .filter_by(id=task_id, user_id=user.id)
        .first()
    )
    if task is None:
        return jsonify({"error": "Task not found."}), 404

    payload = request.get_json(silent=True) or {}

    if "title" in payload:
        title = (payload.get("title") or "").strip()
        if not title:
            return jsonify({"error": "Title cannot be empty."}), 400
        task.title = title

    if "description" in payload:
        task.description = (payload.get("description") or "").strip() or None

    if "start_date" in payload:
        new_start = _parse_iso_date(payload.get("start_date"))
        if payload.get("start_date") and new_start is None:
            return jsonify({"error": "Invalid start_date format."}), 400
        task.start_date = new_start

    if "end_date" in payload:
        new_end = _parse_iso_date(payload.get("end_date"))
        if payload.get("end_date") and new_end is None:
            return jsonify({"error": "Invalid end_date format."}), 400
        task.end_date = new_end

    if "done" in payload:
        task.done = bool(payload.get("done"))

    if "priority" in payload:
        normalized_priority = _normalize_priority(payload.get("priority"))
        if normalized_priority is None:
            valid_options = ", ".join(PRIORITY_LEVELS.keys())
            return (
                jsonify({"error": f"Priority must be one of: {valid_options}."}),
                400,
            )
        task.priority = normalized_priority

    if "goal_id" in payload:
        goal_id = payload.get("goal_id")
        if goal_id is None:
            task.goal_id = None
        else:
            goal = Goal.query.filter_by(id=goal_id, user_id=user.id).first()
            if goal is None:
                return jsonify({"error": "Goal not found for current user."}), 404
            task.goal_id = goal.id

    if "learning_item_id" in payload:
        learning_item_id = payload.get("learning_item_id")
        if learning_item_id is None:
            task.learning_item_id = None
        else:
            learning_item = LearningItem.query.get(learning_item_id)
            if learning_item is None:
                return jsonify({"error": "Learning item not found."}), 404
            task.learning_item_id = learning_item.id

    db.session.commit()

    return jsonify({"task": _serialize_task(task)})


@api_bp.route("/tasks/<int:task_id>", methods=["DELETE"])
@require_jwt(hydrate=True)
def delete_task(task_id: int):
    """删除任务：仅允许删除本人任务。"""
    user, error_response, status = _enforce_user()
    if error_response:
        return error_response, status

    task = Task.query.filter_by(id=task_id, user_id=user.id).first()
    if task is None:
        return jsonify({"error": "Task not found."}), 404

    db.session.delete(task)
    db.session.commit()

    return jsonify({"message": "Task deleted."}), 200
