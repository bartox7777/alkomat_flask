from flask import Blueprint, jsonify, request, abort
from db import get_db
import sqlite3
import sys
import traceback
from datetime import datetime
from helpers import get_readings_internal, check_for_block, get_sober_readings_data, get_sober_readings_histogram, get_blocks_number_data, get_blocks_number_histogram

api = Blueprint('api', __name__)


# Define a route to get readings from the database
@api.route("/get_readings", defaults={"id": None})
@api.route("/get_readings/<id>")
#@login_required  # Add this decorator to protect the route
def get_readings(id):
    try:
        # Get count and offset parameters from the request or use default values
        count = request.args.get("count", default=50, type=int)
        offset = request.args.get("offset", default=0, type=int)
        
        # Try to get readings from the database
        list_of_readings = get_readings_internal(count, offset, id)
        return jsonify(list_of_readings), 200
    except sqlite3.Error as er:
        # If an SQLite error occurs, return the error information as a response
        exc_type, exc_value, exc_tb = sys.exc_info()
        return traceback.format_exception(exc_type, exc_value, exc_tb)[-1], 500
    

@api.route("/check_rfid/<rfid>")
def check_rfid(rfid):
    try:
        db = get_db()
        cur = db.execute("SELECT * FROM users WHERE rfid = ?", (rfid,))
        user = cur.fetchone()
        if user:
            return jsonify({"id": user[0], "name": user[1], "surname": user[2], "blocked": user[3]}), 200
        else:
            abort(404)
    except sqlite3.Error as er:
        abort(404)


# Define a route to add a reading to the database
@api.route("/add_reading/<rfid>/<int:ref_value>/<int:value>", methods=['GET'])
def add_reading(rfid, ref_value, value):
    try:
        # Try to insert the reading into the database
        db = get_db()
        
        # Check if an employee with the given RFID exists
        cur = db.execute("SELECT * FROM USERS WHERE RFID = ?", (rfid,))
        user = cur.fetchone()
        if not user:
            # User does not exist, return error message
            return jsonify({"message": "USER DOESN'T EXIST"}), 404
        
        # Check if an employee is blocked
        cur = db.execute("SELECT BLOCKED FROM USERS WHERE RFID = ?", (rfid,))
        blocked_status = cur.fetchone()
        print(f"Bloked status: {blocked_status[0]}")
        if blocked_status[0] == 1:
            # User is blocked, return error message
            return jsonify({"message": "USER BLOCKED"}), 403
        
        # Insert the reading into the database
        insert_value = 1-value/ref_value
        if insert_value < 0:
            insert_value = 0
        db.execute(
            "INSERT INTO readings (rfid, date_time, value) VALUES (?, ?, ?)",
            (rfid, datetime.now(), round(insert_value,2)),
        )
        db.commit()
        
        # Check if user should be blocked
        try:
            is_drunk = value / ref_value < 0.8 and ref_value - value > 5 and value < 70
            if is_drunk:
                check_for_block(rfid)
                return jsonify({"message": "ENTRY BLOCKED"}), 200
        except Exception as e:
            return jsonify({"message": str(e)}), 500
        
        return jsonify({"message": "ACCEPTED"}), 200
    except sqlite3.Error as er:
        # If an SQLite error occurs, return the error information as a response
        exc_type, exc_value, exc_tb = sys.exc_info()
        return traceback.format_exception(exc_type, exc_value, exc_tb)[-1], 500
    

# Define route to get plots from helpers.py
@api.route("/get_plots")
def get_plots():
    try:
        # Try to get plots from the database
        drunk_threshold = 0.2
        sober_readings_data, timestamp = get_sober_readings_data(drunk_threshold)
        if sober_readings_data == "No records found":
            return jsonify({"message": "No records found"}), 404
        sober_readings_histogram = get_sober_readings_histogram(drunk_threshold=drunk_threshold, histogram_data=sober_readings_data, timestamp=timestamp)
        blocks_number_data = get_blocks_number_data()
        if blocks_number_data == "No records found":
            return jsonify({"message": "No records found"}), 404
        blocks_number_histogram = get_blocks_number_histogram(blocks_number_data)
        return jsonify({"sober_readings_data": sober_readings_data, "sober_readings_histogram": sober_readings_histogram, "blocks_number_data": blocks_number_data, "blocks_number_histogram": blocks_number_histogram}), 200
    except sqlite3.Error as er:
        # If an SQLite error occurs, return the error information as a response
        exc_type, exc_value, exc_tb = sys.exc_info()
        return traceback.format_exception(exc_type, exc_value, exc_tb)[-1], 500
