from datetime import date, datetime, timezone
from pathlib import Path
import json
import os
import tempfile

from flask import Flask, jsonify, request


app = Flask(__name__)

# Store courses.json in the same folder as app.py
COURSES_FILE = Path(__file__).parent / "courses.json"

VALID_STATUSES = {
    "Not Started",
    "In Progress",
    "Completed",
}

REQUIRED_FIELDS = {
    "name",
    "description",
    "target_date",
    "status",
}


def ensure_courses_file():
    """Create courses.json automatically if it does not exist."""
    try:
        if not COURSES_FILE.exists():
            COURSES_FILE.write_text("[]", encoding="utf-8")
    except OSError as error:
        raise RuntimeError(f"Could not create courses.json: {error}")


def load_courses():
    """Read courses from courses.json."""
    ensure_courses_file()

    try:
        with COURSES_FILE.open("r", encoding="utf-8") as file:
            courses = json.load(file)
    except json.JSONDecodeError:
        raise RuntimeError("courses.json contains invalid JSON.")
    except OSError as error:
        raise RuntimeError(f"Could not read courses.json: {error}")

    if not isinstance(courses, list):
        raise RuntimeError("courses.json must contain a JSON list.")

    return courses


def save_courses(courses):
    """Save courses to courses.json."""
    ensure_courses_file()

    temporary_path = None

    try:
        # Write to a temporary file first.
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=COURSES_FILE.parent,
            delete=False,
        ) as temporary_file:
            json.dump(courses, temporary_file, indent=2)
            temporary_file.write("\n")
            temporary_path = temporary_file.name

        # Replace the original file after writing succeeds.
        os.replace(temporary_path, COURSES_FILE)

    except OSError as error:
        if temporary_path and os.path.exists(temporary_path):
            os.remove(temporary_path)

        raise RuntimeError(f"Could not write courses.json: {error}")


def validate_course(data):
    """Return a list of validation errors."""
    errors = []

    if not isinstance(data, dict):
        return ["Request body must be a JSON object."]

    missing_fields = REQUIRED_FIELDS - set(data.keys())

    if missing_fields:
        errors.append(
            "Missing required field(s): "
            + ", ".join(sorted(missing_fields))
        )

    if "name" in data:
        if not isinstance(data["name"], str) or not data["name"].strip():
            errors.append("name must be a non-empty string.")

    if "description" in data:
        if (
            not isinstance(data["description"], str)
            or not data["description"].strip()
        ):
            errors.append("description must be a non-empty string.")

    if "target_date" in data:
        try:
            date.fromisoformat(data["target_date"])
        except (TypeError, ValueError):
            errors.append(
                "target_date must use the YYYY-MM-DD format."
            )

    if "status" in data:
        if data["status"] not in VALID_STATUSES:
            errors.append(
                "status must be one of: "
                "Not Started, In Progress, Completed."
            )

    return errors


def get_next_id(courses):
    """Return the next numeric course ID."""
    if not courses:
        return 1

    ids = [
        course["id"]
        for course in courses
        if isinstance(course.get("id"), int)
    ]

    return max(ids, default=0) + 1


def find_course(courses, course_id):
    """Find a course by ID."""
    for course in courses:
        if course.get("id") == course_id:
            return course

    return None


def timestamp():
    """Return the current UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


@app.errorhandler(RuntimeError)
def handle_runtime_error(error):
    """Return file errors as JSON."""
    return jsonify({
        "error": str(error)
    }), 500


@app.route("/api/courses", methods=["POST"])
def create_course():
    """Create a new course."""
    data = request.get_json(silent=True)
    errors = validate_course(data)

    if errors:
        return jsonify({
            "error": "Validation failed.",
            "details": errors,
        }), 400

    courses = load_courses()

    course = {
        "id": get_next_id(courses),
        "name": data["name"].strip(),
        "description": data["description"].strip(),
        "target_date": data["target_date"],
        "status": data["status"],
        "created_at": timestamp(),
    }

    courses.append(course)
    save_courses(courses)

    return jsonify(course), 201


@app.route("/api/courses", methods=["GET"])
def get_courses():
    """Return all courses."""
    courses = load_courses()
    return jsonify(courses), 200


@app.route("/api/courses/<int:course_id>", methods=["GET"])
def get_course(course_id):
    """Return one course."""
    courses = load_courses()
    course = find_course(courses, course_id)

    if course is None:
        return jsonify({
            "error": f"Course with ID {course_id} was not found."
        }), 404

    return jsonify(course), 200


@app.route("/api/courses/<int:course_id>", methods=["PUT"])
def update_course(course_id):
    """Completely update one course."""
    data = request.get_json(silent=True)
    errors = validate_course(data)

    if errors:
        return jsonify({
            "error": "Validation failed.",
            "details": errors,
        }), 400

    courses = load_courses()
    course = find_course(courses, course_id)

    if course is None:
        return jsonify({
            "error": f"Course with ID {course_id} was not found."
        }), 404

    course["name"] = data["name"].strip()
    course["description"] = data["description"].strip()
    course["target_date"] = data["target_date"]
    course["status"] = data["status"]

    save_courses(courses)

    return jsonify(course), 200


@app.route("/api/courses/<int:course_id>", methods=["DELETE"])
def delete_course(course_id):
    """Delete one course."""
    courses = load_courses()
    course = find_course(courses, course_id)

    if course is None:
        return jsonify({
            "error": f"Course with ID {course_id} was not found."
        }), 404

    courses.remove(course)
    save_courses(courses)

    return jsonify({
        "message": f"Course with ID {course_id} was deleted."
    }), 200


if __name__ == "__main__":
    # Create courses.json before starting the server.
    ensure_courses_file()

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
    )