from flask import Flask
from flask import render_template
from flask import request
from flask import redirect
from flask import url_for
import re
from datetime import datetime
import mysql.connector
from mysql.connector import FieldType
import connect

app = Flask(__name__)

dbconn = None
connection = None


def getCursor():
    global dbconn
    global connection
    connection = mysql.connector.connect(user=connect.dbuser,
                                         password=connect.dbpass, host=connect.dbhost,
                                         database=connect.dbname, autocommit=True)
    dbconn = connection.cursor()
    return dbconn


@app.route("/")
def home():
    return render_template("base.html")


@app.route("/adminview")
def adminview():
    # Add your user view logic here
    return render_template("adminview.html")


@app.route("/listjuniordrivers")
def listjuniordrivers():
    return render_template("listjuniordrivers.html")


@app.route("/driversearch")
def driversearch():
    return render_template("driversearch.html")


@app.route("/editruns")
def editruns():
    return render_template("editruns.html")


@app.route("/overallresults")
def overallresults():
    return render_template("overallresults.html")


@app.route("/listdrivers")
def listdrivers():
    connection = getCursor()
    connection.execute("SELECT * FROM driver;")
    driverList = connection.fetchall()
    print(driverList)
    return render_template("driverlist.html", driver_list=driverList)


@app.route("/driversrundetails")
def driversrundetails():
    connection = getCursor()
    connection.execute("SELECT * FROM driver;")
    driverList = connection.fetchall()
    print(driverList)
    return render_template("driversrundetails.html", driver_list=driverList)


@app.route("/listcourses")
def listcourses():
    connection = getCursor()
    connection.execute("SELECT * FROM course;")
    courseList = connection.fetchall()
    return render_template("courselist.html", course_list=courseList)


@app.route("/showgraph")
def showgraph():
    connection = getCursor()
    # Insert code to get top 5 drivers overall, ordered by their final results.
    # Use that to construct 2 lists: bestDriverList containing the names, resultsList containing the final result values
    # Names should include their ID and a trailing space, eg '133 Oliver Ngatai '

    return render_template("top5graph.html")  #, name_list=bestDriverList, value_list=resultsList)


if __name__ == '__main__':
    app.run()
