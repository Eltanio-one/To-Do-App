# import from libraries
from flask import Flask, flash, redirect, render_template, request, session
from datetime import datetime
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from flask_mail import Mail, Message
import requests
from config import config
from keys import SITE_KEY, SECRET_KEY, MAIL_USERNAME, MAIL_PASSWORD
from psycopg2 import connect, DatabaseError
from re import fullmatch

# import functions from helpers.py
from helpers import *

# define the database parameters globally
PARAMS = config()

# configure application
app = Flask(__name__)

# mail config updates
app.config.update(
    dict(
        DEBUG=True,
        MAIL_SERVER="smtp.gmail.com",
        MAIL_PORT=587,
        MAIL_USE_TLS=True,
        MAIL_USE_SSL=False,
        MAIL_USERNAME=MAIL_USERNAME,
        MAIL_PASSWORD=MAIL_PASSWORD,
    )
)
mail = Mail(app)

# configure session to use the filesystem instead of signed cookies
# here we state that there will not be a permanent session
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# recaptcha configuration
SITE_KEY = SITE_KEY
SECRET_KEY = SECRET_KEY
VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"


# ensure that nothing is cached so that after logging out, pages can't be accessed
@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    # ensure there is no cache upon requests
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    # define the time that a cache expires as 0
    response.headers["Expires"] = 0
    # HTTP/1.0 implmentation of cache-control
    response.headers["Pragma"] = "no-cache"
    # return the response
    return response


# define the app.route for the homepage
@app.route("/")
@login_required
def index():
    # retrieve username from the users table post-registration
    username = "".join(
        fetch_row("""SELECT username FROM users WHERE id = %s""", (session["user_id"],))
    )

    # determine time for index greeting
    now = datetime.now()
    current_time = now.strftime("%H")
    current_time = int(current_time)
    # decide on greeting
    if current_time < 12 and current_time > 5:
        time_response = "Good Morning,"
    elif current_time >= 12 and current_time < 17:
        time_response = "Good Afternoon,"
    else:
        time_response = "Good Evening,"
    # render the homepage with the relevant greeting
    return render_template("index.html", username=username, time_response=time_response)


# define the app.route for logging in
@app.route("/login", methods=["GET", "POST"])
def login():
    # clear the current session and forget any user_id if present
    session.clear()
    # check request method
    # if GET
    if request.method == "GET":
        return render_template("login.html", site_key=SITE_KEY)
    # if POST
    else:
        # check if username provided
        if not request.form.get("username"):
            flash("Please enter a username")
            return render_template("login.html", site_key=SITE_KEY)

        # check if password provided
        if not request.form.get("password"):
            flash("Please enter a password")
            return render_template("login.html", site_key=SITE_KEY)

        # check if recaptcha valid, follow this link for instructions on how to set recaptcha up https://developers.google.com/recaptcha/docs/verify
        # get the response of the form specified in the login.html ("#login_form" in our case).
        response = request.form["g-recaptcha-response"]
        # to verify the response, make a variable that is set to the the verify url+our secret key+the response generated by the form
        # we call .json() on this as we know the users API will return a json object.
        verify_response = requests.post(
            url=f"{VERIFY_URL}?secret={SECRET_KEY}&response={response}"
        ).json()

        # now just verify if the response was a success and dictate which score is passable
        # to see all aspects of the verify_response json object, print(verify_response)
        if verify_response["success"] == False or verify_response["score"] < 0.5:
            flash("ReCaptcha failed!")
            return render_template("login.html", site_key=SITE_KEY)

        # check if username valid (exists)
        username = request.form.get("username")
        password = request.form.get("password")

        # fetch user parameters
        row = fetch_row("""SELECT * FROM users WHERE username = %s""", (username,))
        # check if username is unique i.e. length ofa rows == 1
        # and if that password provided doesnt match the hash that is returned from the db
        if len(row) != 3 or not check_password_hash(row[2], password):
            flash("Invalid username and/or password")
            return render_template("login.html", site_key=SITE_KEY)

        # validity check over, now assign id to session["user_id"]
        session["user_id"] = row[0]

        # redirect the user to their homepage
        return redirect("/")


# define the app.route when registering
@app.route("/register", methods=["GET", "POST"])
def register():
    conn = None
    # if input supplied by user via post
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # check username given
        if not request.form.get("username"):
            flash("Please enter a username")
            return render_template("register.html")

        # check password given
        if not request.form.get("password"):
            flash("Please enter a password")
            return render_template("register.html")

        # check password was confirmed
        if not request.form.get("confirmation"):
            flash("Please confirm your password")
            return render_template("register.html")

        # query database for duplicate
        try:
            conn = connect(
                host="host.docker.internal",
                user="postgres",
                password="postgres",
                dbname="to-do",
                port=5432,
            )
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """SELECT username FROM users WHERE username = %s""",
                        (username,),
                    )
                    dup = cur.fetchone()
                    if dup:
                        if dup[0] == username:
                            flash("Please choose a unique username")
                            return render_template("register.html")
        except (Exception, DatabaseError) as error:
            print(error)

        # check if password matches confirmation
        if password != confirmation:
            flash("Please ensure passwords match")
            return render_template("register.html")

        # hash the password
        hash = generate_password_hash(password, method="pbkdf2:sha256", salt_length=8)

        # insert user into users table
        modify_rows(
            """INSERT INTO users (username, hash) VALUES (%s, %s)""", (username, hash)
        )
        # send user to their homepage
        return redirect("/")

    # if get used to access page
    elif request.method == "GET":
        # render register page
        return render_template("register.html")


# define the app.route for the today notes page
@app.route("/today", methods=["GET", "POST"])
@login_required
def today():
    # if accessing the page via get
    if request.method == "GET":
        rows = reformat_rows(
            fetch_rows(
                """SELECT task FROM today WHERE user_id = %s""", (session["user_id"],)
            )
        )

        # render today template with current rows
        return render_template("today.html", rows=rows)

    # if accessing the page via post
    elif request.method == "POST":
        # check if task inputted
        task = request.form.get("task")
        if not request.form.get("task"):
            flash("Please enter a task")
            return render_template("today.html")
        # add task to db
        modify_rows(
            """INSERT INTO today (user_id, task) VALUES (%s, %s)""",
            (session["user_id"], task),
        )
        # get updated rows to pass to frontend
        rows = reformat_rows(
            fetch_rows(
                """SELECT task FROM today WHERE user_id = %s""", (session["user_id"],)
            )
        )

        # render today template
        return render_template("today.html", rows=rows)


# define the app.route for the projects notes page
@app.route("/projects", methods=["GET", "POST"])
@login_required
def projects():
    # if accessing via get
    if request.method == "GET":
        # collect tasks from db
        tasks = reformat_rows(
            fetch_rows(
                """SELECT task FROM projects WHERE user_id = %s""",
                (session["user_id"],),
            )
        )
        # collect deadlines from db
        deadlines = reformat_rows(
            fetch_rows(
                """SELECT deadline FROM projects WHERE user_id = %s""",
                (session["user_id"],),
            )
        )
        # create rows to send to frontend
        rows = []
        for i, x in enumerate(tasks):
            rows.append({"task": tasks[i], "deadline": deadlines[i]})

        return render_template("projects.html", rows=rows)

    # if accessing via post
    elif request.method == "POST":
        # check if task provided
        task = request.form.get("task")
        if not request.form.get("task"):
            flash("Please enter a task")
            return render_template("projects.html")

        # check if deadline provided is valid
        deadline = request.form.get("deadline")
        if not request.form.get("deadline"):
            flash("Please enter a deadline")
            return render_template("projects.html")
        if not (
            _ := fullmatch(
                r"^(?:(?:31(\/|-|\.)(?:0?[13578]|1[02]))\1|(?:(?:29|30)(\/|-|\.)(?:0?[13-9]|1[0-2])\2))(?:(?:1[6-9]|[2-9]\d)?\d{2})$|^(?:29(\/|-|\.)0?2\3(?:(?:(?:1[6-9]|[2-9]\d)?(?:0[48]|[2468][048]|[13579][26])|(?:(?:16|[2468][048]|[3579][26])00))))$|^(?:0?[1-9]|1\d|2[0-8])(\/|-|\.)(?:(?:0?[1-9])|(?:1[0-2]))\4(?:(?:1[6-9]|[2-9]\d)?\d{2})$",
                deadline,
            )
        ):
            # collect tasks from db
            tasks = reformat_rows(
                fetch_rows(
                    """SELECT task FROM projects WHERE user_id = %s""",
                    (session["user_id"],),
                )
            )
            # collect deadlines from db
            deadlines = reformat_rows(
                fetch_rows(
                    """SELECT deadline FROM projects WHERE user_id = %s""",
                    (session["user_id"],),
                )
            )
            # create rows to send to frontend
            rows = []
            for i, x in enumerate(tasks):
                rows.append({"task": tasks[i], "deadline": deadlines[i]})

            # flash alert
            flash("Please insert a valid date")
            return render_template("projects.html", rows=rows)

        # insert new row into db if deadline in valid format
        modify_rows(
            """INSERT INTO projects (user_id, task, deadline) VALUES (%s, %s, %s)""",
            (
                session["user_id"],
                task,
                deadline,
            ),
        )
        # collect tasks from db
        tasks = reformat_rows(
            fetch_rows(
                """SELECT task FROM projects WHERE user_id = %s""",
                (session["user_id"],),
            )
        )
        # collect deadlines from db
        deadlines = reformat_rows(
            fetch_rows(
                """SELECT deadline FROM projects WHERE user_id = %s""",
                (session["user_id"],),
            )
        )
        # create rows to send to frontend
        rows = []
        for i, x in enumerate(tasks):
            rows.append({"task": tasks[i], "deadline": deadlines[i]})

        return render_template("projects.html", rows=rows)


# personal app.route follows same logic as projects app.route
@app.route("/personal", methods=["GET", "POST"])
@login_required
def personal():
    # if accessing via get
    if request.method == "GET":
        # collect tasks from db
        tasks = reformat_rows(
            fetch_rows(
                """SELECT task FROM personal WHERE user_id = %s""",
                (session["user_id"],),
            )
        )
        # collect deadlines from db
        deadlines = reformat_rows(
            fetch_rows(
                """SELECT deadline FROM personal WHERE user_id = %s""",
                (session["user_id"],),
            )
        )
        # create rows to send to frontend
        rows = []
        for i, x in enumerate(tasks):
            rows.append({"task": tasks[i], "deadline": deadlines[i]})

        return render_template("personal.html", rows=rows)

    # if accessing via post
    elif request.method == "POST":
        # check if task provided
        task = request.form.get("task")
        if not request.form.get("task"):
            flash("Please enter a task")
            return render_template("personal.html")
        # check if deadline provided is valid
        deadline = request.form.get("deadline")
        if not request.form.get("deadline"):
            flash("Please enter a deadline")
            return render_template("personal.html")
        if not (
            _ := fullmatch(
                r"^(?:(?:31(\/|-|\.)(?:0?[13578]|1[02]))\1|(?:(?:29|30)(\/|-|\.)(?:0?[13-9]|1[0-2])\2))(?:(?:1[6-9]|[2-9]\d)?\d{2})$|^(?:29(\/|-|\.)0?2\3(?:(?:(?:1[6-9]|[2-9]\d)?(?:0[48]|[2468][048]|[13579][26])|(?:(?:16|[2468][048]|[3579][26])00))))$|^(?:0?[1-9]|1\d|2[0-8])(\/|-|\.)(?:(?:0?[1-9])|(?:1[0-2]))\4(?:(?:1[6-9]|[2-9]\d)?\d{2})$",
                deadline,
            )
        ):
            tasks = reformat_rows(
                fetch_rows(
                    """SELECT task FROM personal WHERE user_id = %s""",
                    (session["user_id"],),
                )
            )
            deadlines = reformat_rows(
                fetch_rows(
                    """SELECT deadline FROM personal WHERE user_id = %s""",
                    (session["user_id"],),
                )
            )
            rows = []
            for i, x in enumerate(tasks):
                rows.append({"task": tasks[i], "deadline": deadlines[i]})

            flash("Please insert a valid date ")
            return render_template("personal.html", rows=rows)

        modify_rows(
            """INSERT INTO personal (user_id, task, deadline) VALUES (%s, %s, %s)""",
            (
                session["user_id"],
                task,
                deadline,
            ),
        )

        tasks = reformat_rows(
            fetch_rows(
                """SELECT task FROM personal WHERE user_id = %s""",
                (session["user_id"],),
            )
        )
        deadlines = reformat_rows(
            fetch_rows(
                """SELECT deadline FROM personal WHERE user_id = %s""",
                (session["user_id"],),
            )
        )
        rows = []
        for i, x in enumerate(tasks):
            rows.append({"task": tasks[i], "deadline": deadlines[i]})

        return render_template("personal.html", rows=rows)


# work app.route follows same logic as projects app.route
@app.route("/work", methods=["GET", "POST"])
@login_required
def work():
    # if accessing via get
    if request.method == "GET":
        tasks = reformat_rows(
            fetch_rows(
                """SELECT task FROM work WHERE user_id = %s""",
                (session["user_id"],),
            )
        )
        deadlines = reformat_rows(
            fetch_rows(
                """SELECT deadline FROM work WHERE user_id = %s""",
                (session["user_id"],),
            )
        )
        rows = []
        for i, x in enumerate(tasks):
            rows.append({"task": tasks[i], "deadline": deadlines[i]})

        return render_template("work.html", rows=rows)

    # if accessing via post
    elif request.method == "POST":
        # check if task provided
        task = request.form.get("task")
        if not request.form.get("task"):
            flash("Please enter a task")
            return render_template("work.html")

        # check if deadline provided is valid
        deadline = request.form.get("deadline")
        if not request.form.get("deadline"):
            flash("Please enter a deadline")
            return render_template("work.html")
        if not (
            _ := fullmatch(
                r"^(?:(?:31(\/|-|\.)(?:0?[13578]|1[02]))\1|(?:(?:29|30)(\/|-|\.)(?:0?[13-9]|1[0-2])\2))(?:(?:1[6-9]|[2-9]\d)?\d{2})$|^(?:29(\/|-|\.)0?2\3(?:(?:(?:1[6-9]|[2-9]\d)?(?:0[48]|[2468][048]|[13579][26])|(?:(?:16|[2468][048]|[3579][26])00))))$|^(?:0?[1-9]|1\d|2[0-8])(\/|-|\.)(?:(?:0?[1-9])|(?:1[0-2]))\4(?:(?:1[6-9]|[2-9]\d)?\d{2})$",
                deadline,
            )
        ):
            tasks = reformat_rows(
                fetch_rows(
                    """SELECT task FROM work WHERE user_id = %s""",
                    (session["user_id"],),
                )
            )
            deadlines = reformat_rows(
                fetch_rows(
                    """SELECT deadline FROM work WHERE user_id = %s""",
                    (session["user_id"],),
                )
            )
            rows = []
            for i, x in enumerate(tasks):
                rows.append({"task": tasks[i], "deadline": deadlines[i]})

            flash("Please insert a valid date ")
            return render_template("work.html", rows=rows)

        modify_rows(
            """INSERT INTO work (user_id, task, deadline) VALUES (%s, %s, %s)""",
            (
                session["user_id"],
                task,
                deadline,
            ),
        )
        tasks = reformat_rows(
            fetch_rows(
                """SELECT task FROM work WHERE user_id = %s""",
                (session["user_id"],),
            )
        )
        deadlines = reformat_rows(
            fetch_rows(
                """SELECT deadline FROM work WHERE user_id = %s""",
                (session["user_id"],),
            )
        )
        rows = []
        for i, x in enumerate(tasks):
            rows.append({"task": tasks[i], "deadline": deadlines[i]})

        return render_template("work.html", rows=rows)


# only used to GET the about page
@app.route("/about", methods=["GET"])
def about():
    return render_template("about.html")


# define the app.route for the user submitting a message to my pseudo email
@app.route("/email", methods=["POST"])
def email():
    # get variables
    email = request.form.get("email")
    text = request.form.get("message")
    # check presence
    if not request.form.get("email"):
        flash("Please insert your email address")
        return render_template("about.html")
    if not request.form.get("message"):
        flash("Please insert a message")
        return render_template("about.html")
    # check validity of email using regex
    if not (
        _ := fullmatch(
            r"^[a-zA-Z0-9.!#$%&'*+\/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$",
            email,
        )
    ):
        flash("Please insert a valid email address")
        return render_template("about.html")

    # insert message and sender into table
    modify_rows(
        """INSERT INTO mail (user_id, email, message) VALUES (%s, %s, %s)""",
        (session["user_id"], email, text),
    )

    # create and send mail
    message = Message("To-Do Enquiry", sender=email, recipients=[MAIL_USERNAME])
    message.body = text
    mail.send(message)
    flash("Message sent!")
    # render the about template once sent
    return render_template("about.html")


# define the app.route for removing a row from a to-do list
@app.route("/removerow", methods=["POST"])
@login_required
def removerow():
    # if submitted from the projects page
    if request.form["type"] == "projects":
        # get the task from the form
        task = request.form.get("task")

        # delete rows
        modify_rows(
            """DELETE FROM projects WHERE user_id = %s AND task = %s""",
            (session["user_id"], task),
        )
        # collect tasks from db
        tasks = reformat_rows(
            fetch_rows(
                """SELECT task FROM projects WHERE user_id = %s""",
                (session["user_id"],),
            )
        )
        # collect deadlines from db
        deadlines = reformat_rows(
            fetch_rows(
                """SELECT deadline FROM projects WHERE user_id = %s""",
                (session["user_id"],),
            )
        )
        # create rows to pass to frontend
        rows = []
        for i, x in enumerate(tasks):
            rows.append({"task": tasks[i], "deadline": deadlines[i]})

        # re-render the page
        return render_template("projects.html", rows=rows)

    # if submitted from the today page (same as above)
    elif request.form["type"] == "today":
        task = request.form.get("task")

        modify_rows(
            "DELETE FROM today WHERE user_id = %s AND task = %s",
            (session["user_id"], task),
        )

        rows = reformat_rows(
            fetch_rows(
                """SELECT task FROM today WHERE user_id = %s""", (session["user_id"],)
            )
        )

        return render_template("today.html", rows=rows)

    # if submitted from the personal page (same as above)
    elif request.form["type"] == "personal":
        task = request.form.get("task")

        modify_rows(
            """DELETE FROM personal WHERE user_id = %s AND task = %s""",
            (session["user_id"], task),
        )

        tasks = reformat_rows(
            fetch_rows(
                """SELECT task FROM personal WHERE user_id = %s""",
                (session["user_id"],),
            )
        )
        deadlines = reformat_rows(
            fetch_rows(
                """SELECT deadline FROM personal WHERE user_id = %s""",
                (session["user_id"],),
            )
        )
        rows = []
        for i, x in enumerate(tasks):
            rows.append({"task": tasks[i], "deadline": deadlines[i]})

        return render_template("personal.html", rows=rows)

    # if submitted from the work page (same as above)
    elif request.form["type"] == "work":
        task = request.form.get("task")

        modify_rows(
            """DELETE FROM work WHERE user_id = %s AND task = %s""",
            (session["user_id"], task),
        )

        tasks = reformat_rows(
            fetch_rows(
                """SELECT task FROM work WHERE user_id = %s""",
                (session["user_id"],),
            )
        )
        deadlines = reformat_rows(
            fetch_rows(
                """SELECT deadline FROM work WHERE user_id = %s""",
                (session["user_id"],),
            )
        )
        rows = []
        for i, x in enumerate(tasks):
            rows.append({"task": tasks[i], "deadline": deadlines[i]})
        return render_template("work.html", rows=rows)


# define the app.route to clear a to-do list
@app.route("/clearlist", methods=["POST"])
@login_required
def clearlist():
    # if submitted from the projects page
    if request.form["clear_list"] == "projects":
        # delete all rows from relevant db
        modify_rows(
            """DELETE FROM projects WHERE user_id = %s""", (session["user_id"],)
        )

        tasks = reformat_rows(
            fetch_rows(
                """SELECT task FROM projects WHERE user_id = %s""",
                (session["user_id"],),
            )
        )
        deadlines = reformat_rows(
            fetch_rows(
                """SELECT deadline FROM projects WHERE user_id = %s""",
                (session["user_id"],),
            )
        )
        rows = []
        for i, x in enumerate(tasks):
            rows.append({"task": tasks[i], "deadline": deadlines[i]})

        # re-render the current page
        return render_template("projects.html", rows=rows)

    # if submitted from the today page (same as above)
    elif request.form["clear_list"] == "today":
        modify_rows("""DELETE FROM today WHERE user_id = %s""", (session["user_id"],))
        rows = reformat_rows(
            fetch_rows(
                """SELECT task FROM today WHERE user_id = %s""", (session["user_id"],)
            )
        )
        return render_template("today.html", rows=rows)

    # if submitted from the personal page (same as above)
    elif request.form["clear_list"] == "personal":
        modify_rows(
            """DELETE FROM personal WHERE user_id = %s""", (session["user_id"],)
        )

        tasks = reformat_rows(
            fetch_rows(
                """SELECT task FROM personal WHERE user_id = %s""",
                (session["user_id"],),
            )
        )
        deadlines = reformat_rows(
            fetch_rows(
                """SELECT deadline FROM personal WHERE user_id = %s""",
                (session["user_id"],),
            )
        )
        rows = []
        for i, x in enumerate(tasks):
            rows.append({"task": tasks[i], "deadline": deadlines[i]})
        return render_template("personal.html", rows=rows)

    # if submitted from the work page (same as above)
    elif request.form["clear_list"] == "work":
        modify_rows("""DELETE FROM work WHERE user_id = %s""", (session["user_id"],))

        tasks = reformat_rows(
            fetch_rows(
                """SELECT task FROM work WHERE user_id = %s""",
                (session["user_id"],),
            )
        )
        deadlines = reformat_rows(
            fetch_rows(
                """SELECT deadline FROM work WHERE user_id = %s""",
                (session["user_id"],),
            )
        )
        rows = []
        for i, x in enumerate(tasks):
            rows.append({"task": tasks[i], "deadline": deadlines[i]})
        return render_template("work.html", rows=rows)


# define the app.route for logging out
@app.route("/logout")
def logout():
    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
