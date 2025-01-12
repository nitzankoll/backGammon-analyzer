import cv2 
import numpy as np 
import subprocess
import re
import torch

gnubg_path = r"gnubg\gnubg-cli"  # path to gnubg-cli
model_path = r'model.pt'

is_checker = 0
is_white_checker = 1
is_half_board = 2
is_bar = 3

def get_board_index(x_center,y_center,left_board,right_board):
   
    left_board_width=left_board[2]
    right_board_width=right_board[2]

    left_board_min_x=left_board[0] -left_board_width/2
    right_board_min_x=right_board[0] -right_board_width/2

    left_board_max_x=left_board[0]+left_board_width/2
    right_board_max_x=right_board[0]+right_board_width/2

    x_min_bar=left_board[0]+left_board_width/2 # x_min_bar is the minimum x coordinate of the bar
    x_max_bar=right_board[0]-right_board_width/2 # x_max_bar is the maximum x coordinate of the bar

    if x_min_bar< x_center < x_max_bar: #checker is in the bar
        return "bar"
    else:
        if x_center < x_min_bar: #checker is in the left board
            if y_center < left_board[1]: #checker is in the left top quarter
                quarter_start = 13
                normalized_x= (x_center-left_board_min_x)/(left_board_max_x-left_board_min_x)
            else: #checker is in the left bottom quarter
                quarter_start = 7
                normalized_x= (left_board_max_x-x_center)/(left_board_max_x-left_board_min_x)
        else: #checker is in the right board
            if y_center < right_board[1]: #checker is in the right top quarter
                quarter_start = 19
                normalized_x= (x_center-right_board_min_x)/(right_board_max_x-right_board_min_x)
            else: #checker is in the right bottom quarter
                quarter_start = 1
                normalized_x= (right_board_max_x-x_center)/(right_board_max_x-right_board_min_x)

        return quarter_start + int(6*normalized_x)

def lists_to_string(checkers,left_board,right_board):
    # 0 - white chkers in bar
    # 1-24 - chkers position 0 for empty, 1 for black, -1 for white
    # 25 - black chkers in bar
    board=[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0] 
    board_string = ""
    for checker in checkers:
        x_center,y_center,color = checker
        board_index=get_board_index(x_center,y_center,left_board,right_board)
        if board_index != "bar":
            board[board_index]=board[board_index]+color 
        else:
            if color == 1:
                board[0]+=1
            else:
                board[25]+=1

    for pose in board:
        board_string+=str(pose)+" "

    return board_string

def is_black(label):
    if label == is_white_checker:
        return -1
    return 1

def normalize_xy_data(boxes,image):
    image_width=image.shape[0]
    image_height=image.shape[1]
    new_boxes=[]
    for box in boxes:
        x_center, y_center, width, height, conf, label = box
        # Clip the center coordinates to ensure they are within the image bounds
        x_center = min(max(x_center, 0), image_width - 1)
        y_center = min(max(y_center, 0), image_height - 1)
        new_boxes.append((x_center,y_center,width,height,conf,label))
    return new_boxes

def image_to_lists(model,img_path):
    checkers=[]
    board=[]
    bar=[]

    #load image
    image = cv2.imread(img_path, cv2.IMREAD_COLOR) 

    results = model(img_path)
    results.show() # show the picture wuth t=model detactions

    boxes = results.xywh[0].numpy()  # Bounding boxes (x_center, y_center, width, height)
    boxes = normalize_xy_data(boxes,image)

    for box in boxes:
        x_center, y_center, width, height, conf, label = box
        if label == is_half_board:
            board.append((x_center,y_center,width,height))
        elif label == is_bar:
            bar=[(x_center,y_center,width,height)]
        else: 
            checkers.append((x_center,y_center,is_black(label)))
    
    if board[0][0] > board[1][0]:
        left_board= board[1]
        right_board= board[0]
    else:
        left_board= board[0]
        right_board= board[1]

    return checkers, left_board, right_board

def player_output(suggestion_move):
    string_suggestion_move=""
    if suggestion_move[0] == 'No': 
        string_suggestion_move = "no best move found"
    elif suggestion_move[0] == 'There':
        string_suggestion_move= "There are no legal moves"
    else:
        for move in suggestion_move:
            if move[2]: #eating move
                string_suggestion_move+="move " +str(move[1]) + " checker from " + str(move[0][0]) + " to " + str(move[0][1]) + " and eat him" +'\n'
            else:
                string_suggestion_move+="move " +str(move[1]) + " checker from " + str(move[0][0]) + " to " + str(move[0][1]) +'\n'
    return string_suggestion_move

def rotate_point(from_point,to_point,is_rotated):
    if is_rotated:
        if to_point =="off":
            from_point = 25 - int(from_point)
        elif from_point == "bar":
            to_point = 25 - int(to_point)
        else:
            from_point = 25 - int(from_point)
            to_point = 25 - int(to_point)

    return from_point,to_point

def is_board_rotated(turn):
    is_rotated= False
    if turn =="white":
        is_rotated =True

    return is_rotated

def output_handler(gnu_output,turn):
    suggestion_move=[]
    is_rotated=is_board_rotated(turn)  
    parse_output = hint_parser(gnu_output)
    moves = parse_output.split() #split by space
    
    for move in moves:
        if move.count('/') > 1:  # Check if there are more than one '/' in the move (indicating multiple sequential moves)
            # Handle sequential moves without spaces like "24/18*/15*/12*"
            sub_moves = move.split('*')  # Split by '*' to handle each move
            previous_to_point = None  # Variable to track the previous "to" point
            for sub_move in sub_moves:
                if sub_move:  # Avoid empty segments
                    from_point, to_point = map(str.strip, sub_move.split('/'))
                    if previous_to_point:  # If it's not the first move, set "from_point" to the last "to_point"
                        from_point = previous_to_point
                    suggestion_move.append((rotate_point(from_point, to_point, is_rotated), 1, True))
                   
                    previous_to_point = to_point  # Update the "previous_to_point" for the next move
        elif '(' in move:  # Handle repeated moves like "18/17(2)"
            base_move, repeat_count = move.split('(')
            repeat_count = repeat_count.strip(')')
            from_point, to_point = map(str.strip, base_move.split('/'))
            suggestion_move.append((rotate_point(from_point, to_point, is_rotated), repeat_count, False))
        elif '*' in move:  # Handle moves with hits like "8/5*"
            base_move = move.strip('*')
            from_point, to_point = map(str.strip, base_move.split('/'))
            suggestion_move.append((rotate_point(from_point, to_point, is_rotated), 1, True))
        elif '/' in move:  # Regular moves like "bar/24", "24/off", "24/21"
            from_point, to_point = map(str.strip, move.split('/'))  # Split the move into from and to points
            suggestion_move.append((rotate_point(from_point, to_point, is_rotated), 1, False))
        else:
            suggestion_move.append(move)  # Append as-is for unexpected cases

    return suggestion_move

def hint_parser(gnu_output):
    best_move=""
    if "There are no legal moves" in gnu_output:
        best_move ="There are no legal moves"
    else:
        move_match = re.search(r"(\*?\s*\d+\.\s+Cubeful\s+\d-ply\s+([^\n]+)\s+Eq\.:.*)", gnu_output, re.MULTILINE)
        if move_match:
            best_move = move_match.group(2) # This will capture the move part of the string
        else:
            best_move = "No best move found"

    return best_move
        
def get_best_move_gnubg(position_id, dice_rolls,turn):
    # Commands to send to gnubg-cli
    commands = f"""
    new game
    set player 1 name black
    set player 0 name white
    set board simple {position_id}
    set turn {turn}
    set dice {dice_rolls[0]} {dice_rolls[1]}
    hint
    quit
    """

    try:
        # Start gnubg-cli process
        process = subprocess.Popen(
            [gnubg_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )

        # Communicate with gnubg-cli by sending commands
        stdout, stderr = process.communicate(commands)

        """
        # Debug output
        print("GNU Backgammon Output:")
        print(stdout)
        print("Errors (if any):")
        print(stderr)
        """
        return player_output(output_handler(stdout,turn))

    except FileNotFoundError:
        print("Error: gnubg-cli not found. Check the path.")
        return None

    return None


def suggestion_to_server(image_path, player_turn, dice_roll):

    # Load the trained model
    model = torch.hub.load('ultralytics/yolov5', 'custom', path=model_path) # add source='local' if you want to run all locally
    model.conf = 0.6 # confidence threshold

    checkers, left_board, right_board =image_to_lists(model,image_path)
    board_string=lists_to_string(checkers,left_board,right_board)

    best_move = get_best_move_gnubg(board_string, dice_roll,player_turn)

    if best_move:
        print(best_move)
    else:
        best_move = "Could not determine best move."
        print("Could not determine best move.")

    return best_move

#suggestion_to_server(r'C:\Users\Comp\Desktop\projects\backGammon\dataset\images\train\PXL_20241231_135906226.MP.jpg',"white",(3,3))