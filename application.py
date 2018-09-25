import os, requests, json

from flask import Flask, render_template, session, request
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)


# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))


@app.route("/")
def index():
    session["user_id"]=""
    return render_template("login.html")

@app.route("/register", methods=["GET"])
def register():
    return render_template("register.html")

@app.route("/register", methods=["POST"])
def registered():
    username = request.form.get("username")
    password = request.form.get("password")
    if username == "":
        return render_template("error.html", message="No username typed in.")
    if  password == "":
        return render_template("error.html", message="No password typed in.")
    if db.execute("SELECT * FROM users WHERE username = :username", {"username": username}).rowcount != 0:
        return render_template("error.html", message="This username is taken.")
    db.execute("INSERT INTO users (username, password) VALUES (:username, :password)",
               {"username": username, "password": password})
    db.commit()
    users = db.execute("SELECT * FROM users WHERE username = :username", {"username": username}).fetchone();
    session["user_id"] = users.user_id
    return render_template("success.html", message="registered")

@app.route("/log_in", methods=["POST"])
def log_in():
    username = request.form.get("username")
    password = request.form.get("password")
    if username == "":
        return render_template("error.html", message="No username typed in.")
    if password == "":
        return render_template("error.html", message="No password typed in.")
    if db.execute("SELECT * FROM users WHERE username = :username", {"username": username}).rowcount == 0:
        return render_template("error.html", message="No such user exists.")
    users = db.execute("SELECT * FROM users WHERE username = :username", {"username": username}).fetchone();
    if users.password != password:
        return render_template("error.html", message="Wrong password.")
    session["user_id"]= users.user_id
    return render_template("success.html", message="logged in")

@app.route("/search", methods=["GET"])
def search():
    return render_template("search.html", session_id=session["user_id"])

@app.route("/search", methods=["POST"])
def searched():
    s = request.form.get("s").upper()
    results = db.execute("SELECT * FROM books WHERE UPPER(title) LIKE :s OR UPPEr(author) LIKE :s OR UPPER(isbn) LIKE :s", {"s": '%'+s+'%'}).fetchall()
    return render_template("search.html", results=results)

@app.route("/book/<string:isbn>", methods=["GET"])
def book(isbn):
    info = db.execute("SELECT * FROM books WHERE isbn = :isbn", {"isbn": isbn}).fetchone()
    reviews = db.execute("SELECT * FROM reviews WHERE isbn = :isbn", {"isbn": isbn}).fetchall()
    res = requests.get("https://www.goodreads.com/book/review_counts.json",
                       params={"key": "9a7dADL3K5I6mQqAlFXQ", "isbns": isbn})
    user_id = session["user_id"]
    return render_template("book.html", info=info, reviews=reviews, user_id=user_id, res=res)

@app.route("/book/<string:isbn>", methods=["POST"])
def add_rev(isbn):
    if session["user_id"] == "":
        return render_template("login.html");
    if db.execute("SELECT * FROM reviews WHERE user_id = :user_id AND isbn = :isbn", {"user_id": session["user_id"], "isbn": isbn}).rowcount != 0:
        return render_template("error.html", message="You have already added a review for this book.")
    db.execute("INSERT INTO reviews (rating, text, isbn, user_id) VALUES (:rating, :text, :isbn, :user_id)",
               {"rating": request.form.get("rating"), "text": request.form.get("text"), "isbn": isbn, "user_id": session["user_id"]})
    db.commit()
    info = db.execute("SELECT * FROM books WHERE isbn = :isbn", {"isbn": isbn}).fetchone()
    reviews = db.execute("SELECT * FROM reviews WHERE isbn = :isbn", {"isbn": isbn}).fetchall()
    res = requests.get("https://www.goodreads.com/book/review_counts.json",
                       params={"key": "9a7dADL3K5I6mQqAlFXQ", "isbns": isbn})
    return render_template("book.html", info=info, reviews=reviews, res=res)

@app.route("/api/<string:isbn>", methods=["GET"])
def api(isbn):
    if db.execute("SELECT * FROM books WHERE isbn = :isbn", {"isbn": isbn}).rowcount == 0:
        return render_template("error.html", message="404 ISBN not found.")
    book = db.execute("SELECT * FROM books WHERE isbn = :isbn", {"isbn": isbn}).fetchone()
    reviews = db.execute("SELECT * FROM reviews WHERE isbn = :isbn", {"isbn": isbn})
    number = reviews.rowcount
    average = 0
    for review in reviews:
        average += review.rating
    if number != 0:
        average /= number
    data = {"title": book.title, "author": book.author, "year": book.year, "isbn": book.isbn, "review_count": number, "average_score": average}
    json_data = json.dumps(data)
    return json_data

@app.route("/log_out")
def log_out():
    session["user_id"]=""
    return render_template("login.html")
