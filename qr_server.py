from flask import Flask, request
import logic
app = Flask(__name__)


@app.route('/', methods=['POST', 'GET'])
def prime():
    if request.form.get('id') is not None:
        user_id = str(request.form.get('id'))[:-1]
        print(user_id)

        logic.sheets_check_user(user_id)
        return 'ok'
    return 'noo'


if __name__ == '__main__':
    # run app in debug mode on port 5000
    app.run(debug=True, port=5000, host='0.0.0.0')
