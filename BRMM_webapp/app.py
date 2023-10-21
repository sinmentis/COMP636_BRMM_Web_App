from datetime import datetime

import mysql.connector
from flask import Flask, render_template, request, redirect

import connect

app = Flask(__name__)

dbconn = None
connection = None
courses_range = ['A', 'B', 'C', 'D', 'E', 'F']
run_numbers_range = [1, 2]


def calculate_age(birthdate):
    """
    Calculate the age based on the birthdate.

    :param birthdate: The birthdate in 'YYYY-MM-DD' format.
    :return: The age in years.
    """
    age = None
    if birthdate:
        birthdate = datetime.strptime(birthdate, '%Y-%m-%d')
        today = datetime.today()
        age = today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))
    return age


def total_time_sort_key(item):
    """
    Can be used in a sort function to sort drivers based on their results. Sorts qualified drivers by total time
    and places "Not Qualified" entries at the bottom sorted by name.

    :param item: A tuple containing driver details and their results.
    :return: A tuple (sort_key, name) for sorting.
    """
    total_time = item[1]['total_time']
    name = f"{item[1]['surname']} {item[1]['first_name']}"

    if total_time == "Not Qualified":
        # Use 'z' followed by the driver's name to place "Not Qualified" entries at the bottom sorted by name.
        return float('inf'), 'z' + name
    return float(total_time), name


def calculate_run_total_time(cones_hit: int | None, wd: int | None, seconds: int | None) -> int | None:
    """
    Each run total is the driver's time in seconds plus any cone/wrong direction penalties (5 seconds per cone hit, 10 seconds for a WD).
    :param cones_hit: Number of cones hits in one run
    :param wd: If wrong direction ever happens
    :param seconds: real course times
    :return: course time after penalties. Return None if not finished.
    """
    cones_hit_penalties = cones_hit if cones_hit else 0 * 5
    wd_penalties = wd if wd else 0 * 10
    try:
        return seconds + cones_hit_penalties + wd_penalties
    except TypeError:
        return None


def process_overall_results(results):
    """
    Take a list of overall results from SQL and calculate total time.
    :param results: i.e. [('137', 'Celeste', 'Daniel', NULL, 'RWD', 'Camaro', 'Cracked Fluorescent', NULL, '0', '49.47')]
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
            # Create a new record for a new driver
            user_dict[result[0]] = {
                "surname": result[1],
                "first_name": result[2],
                "junior": result[3],
                "drive_class": result[4],
                "model": result[5],
                "courses": {result[6]: new_record}
            }
        else:
            # Add new course record for an old driver if possible and check the best of two
            if result[6] in user_dict[result[0]]["courses"].keys():
                # Check if the new record is better than the existing one
                if not user_dict[result[0]]["courses"][result[6]]:
                    user_dict[result[0]]["courses"][result[6]] = new_record
                elif new_record:
                    user_dict[result[0]]["courses"][result[6]] = min(new_record,
                                                                     user_dict[result[0]]["courses"][result[6]])
            else:
                # Add a new course record
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
    connection = mysql.connector.connect(user=connect.dbuser, password=connect.dbpass, host=connect.dbhost,
                                         database=connect.dbname, autocommit=True)
    dbconn = connection.cursor()
    return dbconn


@app.route("/")
@app.route("/public_view/")
def home():
    return render_template("home.html")


@app.route("/admin_view/")
def admin_view():
    return render_template("home_admin.html")


@app.route("/admin_view/list_junior_drivers/")
def list_junior_drivers():
    connection = getCursor()
    connection.execute("SELECT d1.driver_id, d1.first_name, d1.surname, d2.first_name, d2.surname "
                       "FROM driver AS d1 "
                       "JOIN driver AS d2 ON d1.caregiver = d2.driver_id "
                       "WHERE d1.caregiver IS NOT NULL "
                       "ORDER BY d1.age DESC, d1.surname;")
    junior_driver_list = connection.fetchall()
    return render_template("list_junior_drivers.html", junior_driver_list=junior_driver_list)


@app.route("/admin_view/driver_search/", methods=['GET', 'POST'])
def driver_search():
    search_results = None
    if request.method == 'POST':
        keyword = request.form.get('search_query')
        connection = getCursor()
        connection.execute(f"SELECT * FROM driver WHERE first_name LIKE '%{keyword}%' OR surname LIKE '%{keyword}%';")
        search_results = connection.fetchall()
    return render_template('driver_search.html', search_results=search_results)


@app.route("/admin_view/edit_runs/", methods=['GET', 'POST'])
def edit_runs():
    result_list = None
    if request.method == 'POST':
        search_run_sql_query = f"SELECT md.driver_id, md.surname, md.first_name, mr.crs_id, ms.name, mr.run_num, " \
                               f"mc.model, mc.drive_class, mr.cones, mr.wd, mr.seconds " \
                               f"FROM driver as md " \
                               f"LEFT JOIN car as mc ON mc.car_num = md.car " \
                               f"LEFT JOIN run as mr ON mr.dr_id = md.driver_id " \
                               f"LEFT JOIN course as ms ON mr.crs_id = ms.course_id "

        selected_driver = request.form.get('selected_driver')
        if selected_driver:
            search_run_sql_query += f"WHERE md.driver_id = {selected_driver}"

        selected_course = request.form.get('selected_course')
        if selected_course:
            if selected_driver:
                search_run_sql_query += f" AND mr.crs_id = '{selected_course}'"
            else:
                search_run_sql_query += f"WHERE mr.crs_id = '{selected_course}'"
        search_run_sql_query += ";"
        connection = getCursor()
        connection.execute(search_run_sql_query)
        result_list = connection.fetchall()
    connection = getCursor()
    connection.execute("SELECT driver_id, first_name, surname FROM driver;")
    driver_list = connection.fetchall()
    connection.execute("SELECT course_id, name FROM course;")
    course_list = connection.fetchall()
    return render_template("edit_runs.html", driver_list=driver_list, course_list=course_list, result_list=result_list)


@app.route("/admin_view/edit_run/<int:driver_id>-<int:run_num>-<string:course_id>/", methods=['GET', 'POST'])
def edit_run(driver_id, course_id, run_num):
    message = ""
    if request.method == 'POST':
        edited_cones = request.form.get('cones')
        edited_wd = request.form.get('wd')
        edited_seconds = request.form.get('seconds')

        if edited_cones == "" or edited_cones == "None":
            edited_cones = None
        if edited_wd == "" or edited_wd == "None":
            edited_wd = 0
        if edited_seconds == "" or edited_seconds == "None":
            edited_seconds = None

        connection = getCursor()
        update_query = ("UPDATE run "
                        "SET cones = %s, wd = %s, seconds = %s "
                        "WHERE dr_id = %s AND crs_id = %s AND run_num = %s;")
        connection.execute(update_query, (edited_cones, edited_wd, edited_seconds, driver_id, course_id, run_num))
        message = "Success"

    connection = getCursor()
    connection.execute("SELECT driver_id, first_name, surname FROM driver;")
    driver_list = connection.fetchall()
    connection.execute("SELECT course_id, name FROM course;")
    course_list = connection.fetchall()
    connection.execute(f"SELECT md.driver_id, md.surname, md.first_name, mr.crs_id, ms.name, mr.run_num, "
                       f"mc.model, mc.drive_class, mr.cones, mr.wd, mr.seconds "
                       f"FROM driver as md "
                       f"LEFT JOIN car as mc ON mc.car_num = md.car "
                       f"LEFT JOIN run as mr ON mr.dr_id = md.driver_id "
                       f"LEFT JOIN course as ms ON mr.crs_id = ms.course_id "
                       f"WHERE md.driver_id = %s "
                       f"AND mr.run_num = %s "
                       f"AND mr.crs_id = %s;", (driver_id, run_num, course_id))
    run_result = connection.fetchone()
    return render_template("edit_run.html", driver_list=driver_list, course_list=course_list, run_result=run_result,
                           message=message)


@app.route("/admin_view/add_driver/")
def add_driver():
    return render_template("add_driver.html")


@app.route("/admin_view/add_driver/<int:junior>/", methods=['GET', 'POST'])
def add_driver2(junior):
    connection = getCursor()

    # Retrieve eligible caregivers (age > 25)
    connection.execute("SELECT driver_id, first_name, surname FROM driver "
                       "WHERE age > 25 OR age IS NULL;")  # Assume Null means valid caregivers
    eligible_caregivers = connection.fetchall()

    # Retrieve All cars
    connection.execute("SELECT * FROM car;")
    existing_cars = connection.fetchall()
    message = None  # Error display style will be used when Keyword "Error: " detected
    try:
        if request.method == 'POST':
            # Check if caregiver is selected for junior driver
            caregiver = request.form.get('caregiver')
            if junior and caregiver == "":
                raise Exception("Junior driver must assign a valid caregiver")

            date_of_birth = request.form.get('date_of_birth')
            if date_of_birth == "":
                raise Exception("Date of Birth can't be Empty")
            age = calculate_age(date_of_birth)

            first_name = request.form.get('first_name')
            surname = request.form.get('surname')
            if first_name == "" or surname == "":
                raise Exception("name can't be Empty")

            car = request.form.get('car')
            if car == "":
                raise Exception("Driver must assign a valid car")

            # Insert the new driver into the "driver" table
            insert_driver_query = "INSERT INTO driver (first_name, surname, date_of_birth, age, caregiver, car)" \
                                  "VALUES (%s, %s, %s, %s, %s, %s);"
            connection.execute(insert_driver_query, (first_name, surname, date_of_birth, age, caregiver, car))

            # Get the new driver ID from the last inserted row
            connection.execute("SELECT LAST_INSERT_ID();")
            new_driver_id = connection.fetchone()[0]

            # Update run table for new driver with default value
            for course in courses_range:
                for run_number in run_numbers_range:
                    connection.execute("INSERT INTO run (dr_id, crs_id, run_num, seconds, cones, wd) "
                                       "VALUES (%s, %s, %s, NULL, NULL, 0);",
                                       (new_driver_id, course, run_number))
            message = f"Driver added successfully with ID: {new_driver_id}"
    except Exception as e:
        message = f"Error: {e}"
    return render_template("add_driver2.html", eligible_caregivers=eligible_caregivers, existing_cars=existing_cars,
                           message=message, junior=junior)


@app.route("/public_view/overall_results/")
def overall_results():
    """
    Show the overall results in a table, from best to worst overall result, and with any NQ results at the bottom (at
    the bottom of the list or as a note below the table). The table will include the driver ID and names (including
    '(J)' for juniors), and car model. Display all 6 course times for each driver, as well as their overall result.
    The winner should display “cup” next to their result, and the next 4 display “prize” (just the text is fine,
    or optionally suitable alternative symbols).
    """
    connection = getCursor()
    connection.execute("SELECT d.driver_id, d.surname, d.first_name, d.caregiver, "
                       "c.drive_class, c.model, s.name, "
                       "r.cones, r.wd, r.seconds "
                       "FROM driver as d "
                       "INNER JOIN car as c ON c.car_num = d.car "
                       "INNER JOIN run as r ON r.dr_id = d.driver_id "
                       "INNER JOIN course as s ON r.crs_id = s.course_id "
                       "ORDER BY s.name;")

    overall_results = process_overall_results(connection.fetchall())

    # Get list of course for display
    connection.execute("SELECT name FROM course ORDER BY name;")
    course_names = connection.fetchall()
    course_names = [row[0] for row in course_names]
    return render_template("overall_results.html", overall_results=overall_results, course_names=course_names)


@app.route("/public_view/list_drivers/")
def list_drivers():
    """
    Modify the /list_drivers route so that each driver’s car details are also displayed. Do not display the car_num.
    Show them in surname then first name order, and use Bootstrap to display the junior drivers in yellow. Make the
    driver name a clickable link that also displays the driver’s run details page
    """
    connection = getCursor()
    connection.execute("SELECT md.driver_id, md.surname, md.first_name, mc.model, mc.drive_class, md.caregiver FROM "
                       "driver as md LEFT JOIN car as mc ON mc.car_num = md.car "
                       "ORDER BY md.surname, md.first_name;")
    driver_list = connection.fetchall()
    return render_template("driver_list.html", driver_list=driver_list)


@app.route('/public_view/drivers_run_details/<int:driver_id>/', methods=['GET'])
def drivers_run_details_page(driver_id):
    """
    :param driver_id: Driver's ID to display information about
    """
    connection = getCursor()
    connection.execute("SELECT * FROM driver;")
    driver_list = connection.fetchall()
    # Fetch driver's details based on the driver_id parameter
    connection.execute(f"SELECT md.driver_id, md.surname, md.first_name, mc.model, mc.drive_class, "
                       f"ms.name, mr.run_num, mr.cones, mr.wd, mr.seconds FROM driver as md "
                       f"LEFT JOIN car as mc ON mc.car_num = md.car "
                       f"LEFT JOIN run as mr ON mr.dr_id = md.driver_id "
                       f"LEFT JOIN course as ms ON mr.crs_id = ms.course_id "
                       f"WHERE md.driver_id = %s;", (driver_id,))
    selected_driver_details = connection.fetchall()
    return render_template('drivers_run_details.html', driver_list=driver_list, selected_driver=selected_driver_details)


@app.route('/public_view/drivers_run_details/', methods=['GET', 'POST'])
def drivers_run_details():
    """
    A driver's name is selected from a drop-down list of drivers to display a
    page showing the driver's run details and run totals, including the course names (but not the
    course ID letter). Include the driver ID and names, and car model and drive class, as headings.
    """
    connection = getCursor()
    connection.execute("SELECT * FROM driver;")
    driver_list = connection.fetchall()

    if request.method == 'POST':
        selected_driver_id = request.form.get('selected_driver')
        if selected_driver_id:
            # Construct the URL for the individual run details page
            url = f"/public_view/drivers_run_details/{selected_driver_id}"
            return redirect(url)
    return render_template('drivers_run_details.html', driver_list=driver_list)


@app.route("/public_view/list_courses/")
def list_courses():
    """
    Make the course_list page display the course’s image, rather than the name of
    the image file.
    """
    connection = getCursor()
    connection.execute("SELECT * FROM course;")
    course_list = connection.fetchall()
    return render_template("course_list.html", course_list=course_list)


@app.route("/public_view/show_graph/")
def show_graph():
    """
    Bar graph: Display a horizontal bar graph of the top 5 drivers overall. using driver names and overall results as
    passed variables instead of hard-coded constants.
    """
    connection = getCursor()

    # Query the database to get overall results, including driver details and course times
    connection.execute("SELECT d.driver_id, d.surname, d.first_name, d.caregiver, "
                       "c.drive_class, c.model, s.name, "
                       "r.cones, r.wd, r.seconds "
                       "FROM driver as d "
                       "INNER JOIN car as c ON c.car_num = d.car "
                       "INNER JOIN run as r ON r.dr_id = d.driver_id "
                       "INNER JOIN course as s ON r.crs_id = s.course_id "
                       "ORDER BY s.name;")

    overall_results = process_overall_results(connection.fetchall())[:5]

    # Extract driver names and overall results
    driver_names = [f"{driver[1]['surname']} {driver[1]['first_name']}" for driver in overall_results]
    overall_results = [driver[1]['total_time'] for driver in overall_results]
    return render_template("top5graph.html", driver_names=driver_names, overall_results=overall_results)


@app.errorhandler(404)
@app.errorhandler(500)
def error_handler(error):
    error_message = "An error occurred. Please try again later."
    if error.code == 404:
        error_message = "The requested page was not found."

    return render_template('error.html', error_message=error_message), error.code


if __name__ == '__main__':
    app.run()
