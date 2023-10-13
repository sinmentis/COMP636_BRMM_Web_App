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


def total_time_sort_key(item):
    total_time = item[1]['total_time']
    if total_time == "Not Qualified":
        return float('inf')  # Put "Not Qualified" entries at the bottom
    return float(total_time)


def calculate_run_total_time(cones_hit: int | None, wd: int | None, second: int | None) -> int | None:
    """
    Each run total is the driver's time in seconds plus any cone/wrong direction penalties (5 seconds per cone hit, 10 seconds for a WD).
    :param cones_hit: Number of cones hits in one run
    :param wd: If wrong direction ever happens
    :param second: real course times
    :return: course time after penalties. Return None if not finished.
    """
    cones_hit_penalties = cones_hit if cones_hit else 0 * 5
    wd_penalties = wd if wd else 0 * 10
    try:
        return second + cones_hit_penalties + wd_penalties
    except TypeError:

        return None


def process_overall_results(results):
    """
    Take a list of overall results from SQL and calculate total time.
    :param results: i.e. [(137, 'Celeste', 'Daniel', 'RWD', 'Camaro', 1, None, 0, None)]
    :return: user_dict["driver ID"]
        {
            "surname": surname,
            "first_name": first_name,
            "junior": caregiver,
            "drive_class": drive_class,
            "model": model,
            "courses": {"course name": results},
            "total_time": total_time
        }
    """
    user_dict = {}
    for result in results:
        new_record = calculate_run_total_time(result[7], result[8], result[9])
        if result[0] not in user_dict.keys():
            # Create a new record for new driver
            user_dict[result[0]] = {
                "surname": result[1],
                "first_name": result[2],
                "junior": result[3],
                "drive_class": result[4],
                "model": result[5],
                "courses": {result[6]: new_record}
            }
        else:
            # Add new course record for old driver if possible, and check best of two
            if result[5] in user_dict[result[0]]["courses"].keys():
                # Check if new record is better than exist one
                if not user_dict[result[0]]["courses"][result[6]]:
                    user_dict[result[0]]["courses"][result[6]] = new_record
                elif new_record:
                    user_dict[result[0]]["courses"][result[6]] = min(new_record,
                                                                     user_dict[result[0]]["courses"][result[6]])
            else:
                # Add new course record
                user_dict[result[0]]["courses"][result[6]] = new_record

    # Calculate total run time
    for user in user_dict.keys():
        try:
            user_dict[user]["total_time"] = sum([value for value in user_dict[user]["courses"].values()])
        except TypeError:
            user_dict[user]["total_time"] = "Not Qualified"

    user_dict = sorted(user_dict.items(), key=total_time_sort_key)
    return user_dict


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
    connection = getCursor()
    connection.execute("SELECT d1.driver_id, d1.first_name, d1.surname, d2.first_name, d2.surname "
                       "FROM driver AS d1 "
                       "JOIN driver AS d2 ON d1.caregiver = d2.driver_id "
                       "WHERE d1.caregiver IS NOT NULL "
                       "ORDER BY d1.age DESC, d1.surname;")
    junior_driver_list = connection.fetchall()

    # i.e. junior_driver_list = [(129, 'Jack', 'Atwood', 'Maggie', 'Atwood')]
    return render_template("listjuniordrivers.html", junior_driver_list=junior_driver_list)


@app.route("/adminview/driversearch")
def driversearch():
    return render_template("driversearch.html")


@app.route("/adminview/editruns")
def editruns():
    return render_template("editruns.html")


@app.route("/overallresults")
def overallresults():
    """
    Show the overall results in a table, from best to worst overall result, and with any NQ results at the bottom (at
    the bottom of the list or as a note below the table). The table will include the driver ID and names (including
    '(J)' for juniors), and car model. Display all 6 course times for each driver, as well as their overall result.
    The winner should display “cup” next to their result, and the next 4 display “prize” (just the text is fine,
    or optionally suitable alternative symbols).
    """
    connection = getCursor()

    # Query the database to get overall results, including driver details and course times
    connection.execute("SELECT d.driver_id, d.surname, d.first_name, d.caregiver, "
                       "c.drive_class, c.model, s.name, "
                       "r.cones, r.wd, r.seconds "
                       "FROM motorkhana.driver as d "
                       "INNER JOIN motorkhana.car as c ON c.car_num = d.car "
                       "INNER JOIN motorkhana.run as r ON r.dr_id = d.driver_id "
                       "INNER JOIN motorkhana.course as s ON r.crs_id = s.course_id "
                       "ORDER BY s.name;")

    overall_results = process_overall_results(connection.fetchall())

    # Get list of course for display
    connection.execute("SELECT name FROM motorkhana.course ORDER BY name;")
    course_names = connection.fetchall()
    course_names = [row[0] for row in course_names]
    return render_template("overallresults.html", overall_results=overall_results, course_names=course_names)


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
    """
    Bar graph: Display a horizontal bar graph of the top 5 drivers overall. using driver names and overall results as
    passed variables instead of hard-coded constants.
    """
    connection = getCursor()

    # Query the database to get overall results, including driver details and course times
    connection.execute("SELECT d.driver_id, d.surname, d.first_name, d.caregiver, "
                       "c.drive_class, c.model, s.name, "
                       "r.cones, r.wd, r.seconds "
                       "FROM motorkhana.driver as d "
                       "INNER JOIN motorkhana.car as c ON c.car_num = d.car "
                       "INNER JOIN motorkhana.run as r ON r.dr_id = d.driver_id "
                       "INNER JOIN motorkhana.course as s ON r.crs_id = s.course_id "
                       "ORDER BY s.name;")

    overall_results = process_overall_results(connection.fetchall())[:5]

    # Extract driver names and overall results
    driver_names = [f"{driver[1]['surname']} {driver[1]['first_name']}" for driver in overall_results]
    overall_results = [driver[1]['total_time'] for driver in overall_results]

    return render_template("top5graph.html", driver_names=driver_names, overall_results=overall_results)


if __name__ == '__main__':
    app.run()
