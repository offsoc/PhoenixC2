import uuid
from flask import (
    Blueprint,
    render_template,
    request,
    session,
    jsonify,
    redirect,
    flash,
    escape,
    abort
)
from Utils.ui import log
from Utils.web import authorized, admin, get_current_user, generate_response
from Database import db_session, UserModel


users_bp = Blueprint("users", __name__, url_prefix="/users")


@users_bp.route("/", methods=["GET"])
@authorized
def get_users():
    use_json = request.args.get("json", "").lower() == "true"
    curr_user = get_current_user()
    users: list[UserModel] = db_session.query(UserModel).all()
    data = [user.to_json() for user in users]
    if curr_user.admin:
        for index, user in enumerate(users):
            if user.admin and not curr_user.username == "phoenix" \
                and not curr_user.username == user.username:
                continue
            data[index]["api_key"] = user.api_key

    return jsonify({"status": "success", "users": data}) if use_json else render_template("users.html", user=curr_user, users=users)


@users_bp.route("/add", methods=["POST"])
@admin
def add_user():
    use_json = request.args.get("json", "").lower() == "true"
    username = request.form.get("username")
    password = request.form.get("password")
    admin = request.form.get("admin", "").lower() == "true"
    disabled = request.form.get("disabled", "").lower() == "true"

    if not username or not password:
        if not use_json:
            flash("Username and password required.")
            redirect("/users")
        return jsonify({"status": "error", "message": "Username and password required."})

    # Check if user exists
    if db_session.query(UserModel).filter_by(username=username).first():
        return generate_response("error", "User already exists.", "users", 403)

    user = UserModel(
        username=username,
        admin=admin,
        disabled=disabled,
        api_key=str(uuid.uuid1()))
    user.set_password(password)

    db_session.add(user)
    db_session.commit()
    log(f"({get_current_user().username}) added {'Admin' if admin else 'User'} {username}.", "success")
    return generate_response("success", f"{'Admin' if admin else 'User'} {username} added.", "users")


@users_bp.route("/remove", methods=["DELETE"])
@admin
def delete_user():
    use_json = request.args.get("json", "").lower() == "true"
    username = request.form.get("username")
    current_user = get_current_user()
    if not username:
        if not use_json:
            flash("Username required.")
            abort
        return jsonify({"status": "error", "message": "Username required."})
    # Check if user exists
    user: UserModel = db_session.query(UserModel).first()
    if user is None:
        return generate_response("error", "User doesn't exist.", "users", 400)

    # Check if user is head admin
    if username == "phoenix":
        return generate_response("error", "Can't delete the Phoenix Account.", "users", 403)

    # Check if user is the operator
    if username == current_user:
        return generate_response("error", "Can't delete your own Account.", "users")

    # Delete user
    db_session.delete(user)
    log(f"({get_current_user().username}) deleted {'Admin' if user.admin else 'User'} {username}.", "success")
    return generate_response("success", f"Deleted {'Admin' if user.admin else 'User'} {username}", "users")


@users_bp.route("/edit", methods=["POST"])
@admin
def edit_user():
    use_json = request.args.get("json", "").lower() == "true"
    username = request.form.get("username", "")
    change = request.form.get("change", "").lower()
    value = request.form.get("value", "")
    if not all([username, change, value]) and change != "api-key":
        if not use_json:
            flash("Username, change and value required.", "error")
            return redirect("/users")
        return jsonify({"status": "error", "message": "Username, change and value required."})
    # Check if user exists
    current_user = get_current_user()
    user: UserModel = db_session.query(
        UserModel).filter_by(username=username).first()
    if user is None:
        return generate_response("error", "User doesn't exist.", "users", 400)

    # Check if user is head admin
    if username == "phoenix" and current_user != "phoenix":
        return generate_response("error", "Can't edit the Phoenix Account.", "users", 403)
    # Edit user
    if change == "admin" and username != "phoenix":
        user.admin = value.lower() == "true"
        db_session.commit()
        log(f"({current_user}) updated {username}'s permissions to {'Admin' if user.admin else 'User'}.", "success")
        return generate_response("success", f"Updated {username}'s permissions to {'Admin' if user.admin else 'User'}.", "users")

    elif change == "password" and len(value) >= 1:
        user.set_password(value)
        db_session.commit()
        log(f"({current_user}) updated {username}'s password.", "success")
        return generate_response("success", f"Updated {username}'s username to {value}.", "users")

    elif change == "username" and username != "phoenix":
        if db_session.query(UserModel).filter_by(username=value).first() or value == "":
            return generate_response("error", "Name is already in use.", "users", 400)
        user = str(escape(value))
        db_session.commit()
        log(f"({current_user}) updated {user}'s username to {value}.", "success")
        return generate_response("success", f"Updated {username}'s username to {value}.", "users")

    elif change == "disabled" and username != "phoenix":
        user.disabled = value.lower() == "true"
        db_session.commit()
        log(f"({current_user}) disabled {'Admin' if user.admin else 'User'} {user}", "success")
        return generate_response("success", f"Disabled {user}.", "users")

    elif change == "api-key":
        user.api_key = str(uuid.uuid1())
        log(f"({current_user}) changed {user}'s api-key.")
        if not use_json:
            flash(
                f"Updated {username}'s api-key to {user.api_key}.", "success")
            return redirect("/users")
        return jsonify({"status": "success", "message": f"Updated {username}'s api-key", "api-key": user.api_key})

    else:
        return generate_response("error", "Invalid change.", "users", 400)