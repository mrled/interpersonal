from flask import (
    Blueprint,
    make_response,
    render_template,
)


bp = Blueprint("root", __name__, template_folder="temple")


@bp.route("/")
def index():
    return render_template("root.index.html.j2")


@bp.route("/hello")
def hello():
    response = make_response(
        "Hello from Interpersonal, the connection between my little site and the indie web",
        200,
    )
    response.mimetype = "text/plain"
    return response