from flask import render_template
from ioos_catalog import app

@app.route('/help', methods=['GET'])
def help():
    return render_template('help.html')

@app.route('/help/feedback', methods=['GET'])
def feedback():
    return render_template('feedback.html')
