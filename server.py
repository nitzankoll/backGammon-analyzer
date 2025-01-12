from flask import Flask, request, jsonify, send_file
import os
from werkzeug.utils import secure_filename
import backgammon

app = Flask(__name__)

# Ensure the upload directory exists
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def analyze_backgammon_image(image_path, player_turn, dice_roll):
    move =  backgammon.suggestion_to_server(image_path, player_turn, dice_roll)
    return move

@app.route('/')
def home():
    return send_file('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
        
        player_turn = request.form.get('playerTurn', 'white')
        dice_roll1 = request.form.get('diceRoll1', '1')
        dice_roll2 = request.form.get('diceRoll2', '1')
        
        if file:
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Analyze the uploaded image
            move = analyze_backgammon_image(filepath, player_turn, (dice_roll1, dice_roll2))
            
            return jsonify({'move': move.split('\n')}), 200
            #return jsonify({'move': move}), 200
    except Exception as e:
        app.logger.error(f"Error processing upload: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0',port=5000)
