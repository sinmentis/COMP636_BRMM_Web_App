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

"""
Tasks:
1. Formatting
2. Naming
3. SQL structure
4. Web structure
5. Code structure
"""

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


@app.route("/adminview/listjuniordrivers")
def listjuniordrivers():
    return render_template("listjuniordrivers.html")


@app.route("/adminview/driversearch")
def driversearch():
    return render_template("driversearch.html")


@app.route("/adminview/editruns")
def editruns():
    return render_template("editruns.html")


@app.route("/overallresults")
def overallresults():
    return render_template("overallresults.html")


@app.route("/listdrivers")
def listdrivers():
    """
    Modify the /listdrivers route so that each driver’s car details are also displayed. Do not display the car_num.
    Show them in surname then first name order, and use Bootstrap to display the junior drivers in yellow. Make the
    driver name a clickable link that also displays the driver’s run details page
    """
    connection = getCursor()
    connection.execute("SELECT md.driver_id, md.surname, md.first_name, mc.model, mc.drive_class, md.caregiver FROM "
                       "motorkhana.driver as md LEFT JOIN motorkhana.car as mc ON mc.car_num = md.car "
                       "ORDER BY md.surname, md.first_name;")
    driverList = connection.fetchall()
    return render_template("driverlist.html", driver_list=driverList)


@app.route('/driversrundetails/<int:driver_id>', methods=['GET'])
def driversrundetailspage(driver_id):
    """
    :param driver_id: Driver's ID to display information about
    """
    connection = getCursor()
    connection.execute("SELECT * FROM driver;")
    driverList = connection.fetchall()


    """
    TODO: Might be better to handle time calculation etc in python instead of using SQL or frontend.
    """
    # Fetch driver's details based on the driver_id parameter
    connection.execute(f"SELECT md.driver_id, md.surname, md.first_name, ms.name, mr.run_num, mc.model, "
                       f"mc.drive_class, mr.cones, mr.wd, mr.seconds FROM motorkhana.driver as md "
                       f"LEFT JOIN motorkhana.car as mc ON mc.car_num = md.car "
                       f"LEFT JOIN motorkhana.run as mr ON mr.dr_id = md.driver_id "
                       f"LEFT JOIN motorkhana.course as ms ON mr.crs_id = ms.course_id "
                       f"WHERE md.driver_id = %s;", (driver_id,))
    selected_driver_details = connection.fetchall()

    return render_template('driversrundetails.html', driver_list=driverList, selected_driver=selected_driver_details)


@app.route('/driversrundetails', methods=['GET', 'POST'])
def driversrundetails():
    """
    A driver's name is selected from a drop-down list of drivers to display a
    page showing the driver's run details and run totals, including the course names (but not the
    course ID letter). Include the driver ID and names, and car model and drive class, as headings.
    """
    connection = getCursor()
    connection.execute("SELECT * FROM driver;")
    driverList = connection.fetchall()

    if request.method == 'POST':
        # Handle the form submission here
        selected_driver_id = request.form.get('selected_driver')
        if selected_driver_id:
            # Construct the URL for the individual run details page
            url = f"/driversrundetails/{selected_driver_id}"
            return redirect(url)

    return render_template('driversrundetails.html', driver_list=driverList)


@app.route("/listcourses")
def listcourses():
    """
    Make the courselist page display the course’s image, rather than the name of
    the image file.
    """
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

    return render_template("top5graph.html")  # , name_list=bestDriverList, value_list=resultsList)


if __name__ == '__main__':
    app.run()
