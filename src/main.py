#!/usr/bin/env python

import cv2, pytesseract, ffmpeg, os, sys, argparse, re

def apply_overlay(side, video_file):
    # To keep the input and output files organized, we will create an 'out'
    # directory if it does not exist already.
    if not os.path.exists("out"):
        os.makedirs("out")

    # Our input file is the video file, and our output file will be the same
    # name as the input file, but with '.out.mp4' appended to the end, and
    # stored in the 'out' directory. The overlay file is the arrow image
    # corresponding to the color of the side of the fencer.
    input_file = video_file

    # Extract file extension from video file.
    file_extension = os.path.splitext(video_file)[1]
    output_file = os.path.join("out", os.path.basename(video_file).replace(file_extension, ".out" + file_extension))
    overlay_file = f"assets/arrows/{side}.png"

    input_stream = ffmpeg.input(input_file)
    overlay_stream = ffmpeg.input(overlay_file)

    output = ffmpeg.filter([input_stream.video, overlay_stream], 'overlay', x='(W-w)/2', y='20')

    ffmpeg.output(output, output_file).overwrite_output().run()

if __name__ == "__main__":
    # Set the path to the Tesseract executable.
    pytesseract.pytesseract.tesseract_cmd = r"/usr/bin/tesseract"

    # Since we are expecting two arguments, we will use the argparse module
    # to parse the command line arguments.
    # Each argument can contain multiple values, so we will use the nargs
    # argument to specify that the argument can contain multiple values.
    parser = argparse.ArgumentParser(description='FFWF - Find Fencer Within Frame')
    parser.add_argument('--video', nargs='+', help='video file(s)', required=True)
    parser.add_argument('--name', nargs='+', type=str, help='fencer name', required=True)
    parser.add_argument('--verbose', action='store_true', help='debug mode')

    args = parser.parse_args()

    video_files = args.video
    fencer_to_detect = args.name

    # Convert the fencer name to lowercase, since this is easier to compare
    # with the text extracted from the video frames.
    fencer_to_detect = [name.lower() for name in fencer_to_detect]

    if video_files is None or fencer_to_detect is None:
        print(f"Error: Missing required arguments.", file=sys.stderr)
        sys.exit(1)

    if fencer_to_detect is None or len(fencer_to_detect) != 2:
        print(f"Error: Invalid fencer name '{fencer_to_detect}'.", file=sys.stderr)
        sys.exit(1)

    print(f"Video files: {video_files}")
    print(f"Fencer to detect: {fencer_to_detect}")

    for video_file in video_files:
        # Load the video file
        try:
            cap = cv2.VideoCapture(video_file)
        except:
            print(f"Error: Could not load the video file '{video_file}'.", file=sys.stderr)
            sys.exit(1)

        # Since the name of the fencer is displayed on the left and right sides
        # (depending on the starting position), we need to crop the left and right
        # sides of the frame and apply OCR on them
        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        bottom_left_x, bottom_left_y, bottom_left_w, bottom_left_h = 0, frame_height - frame_height//4, frame_width//2, frame_height
        bottom_right_x, bottom_right_y, bottom_right_w, bottom_right_h = frame_width//2, frame_height - frame_height//4, frame_width, frame_height

        # Some clips from The Fencing Database (www.fencingdatabase.com/) have
        # the scoreboard overlay located in the top left corner of the video.
        # Therefore, we also need to scan this area of the frames.
        top_left_x, top_left_y, top_left_w, top_left_h = 0, 0, frame_width//10, frame_height//4
        top_right_x, top_right_y, top_right_w, top_right_h = frame_width//10, 0, frame_width//10, frame_height//4

        # To make it a bit easier to see the bounding boxes (for ourselves),
        # we will use different colors for the left and right bounding boxes.
        # Just like in fencing, the left side is red and the right side is green
        left_box_color = (0, 0, 255)  # Red
        right_box_color = (0, 255, 0) # Green

        # Later on we want to break the loop if the fencer is detected,
        # so we can move on to the next video file, if any are left.
        # We will use this variable to keep track of whether the fencer
        # has been detected or not.
        fencer_detected = False

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            # Since we want two bounding boxes, one for the left side and
            # one for the right side, we need to crop the left and right.
            # Here we store the bounding boxes in two separate variables,
            # corresponding to there 'region of interest' (ROI).
            bottom_left_roi = frame[bottom_left_y:bottom_left_y+bottom_left_h, bottom_left_x:bottom_left_x+bottom_left_w]
            bottom_right_roi = frame[bottom_right_y:bottom_right_y+bottom_right_h, bottom_right_x:bottom_right_x+bottom_right_w]
            top_left_roi = frame[top_left_y:top_left_y+top_left_h, top_left_x:top_left_x+top_left_w]
            top_right_roi = frame[top_right_y:top_right_y+top_right_h, top_right_x:top_right_x+top_right_w]

            # Convert the left and right cropped frames to grayscale
            bottom_left_gray = cv2.cvtColor(bottom_left_roi, cv2.COLOR_BGR2GRAY)
            bottom_right_gray = cv2.cvtColor(bottom_right_roi, cv2.COLOR_BGR2GRAY)
            top_left_gray = cv2.cvtColor(top_left_roi, cv2.COLOR_BGR2GRAY)
            top_right_gray = cv2.cvtColor(top_right_roi, cv2.COLOR_BGR2GRAY)

            # Apply OCR on the left and right cropped frames
            bottom_left_text = pytesseract.image_to_string(bottom_left_gray)
            bottom_right_text = pytesseract.image_to_string(bottom_right_gray)
            top_left_text = pytesseract.image_to_string(top_left_gray)
            top_right_text = pytesseract.image_to_string(top_right_gray)

            # Since OpenCV will not detect the fencer's full name all the time,
            # we need to check whether the first OR last name is present in the
            # text. If so, we can assume that the fencer is present in the frame.
            # Therefore, we will need to split the detected text into words and
            # check whether the first or last name is present in the text.
            bottom_left_text = bottom_left_text.lower().split()
            bottom_right_text = bottom_right_text.lower().split()
            top_left_text = top_left_text.lower().split()
            top_right_text = top_right_text.lower().split()

            print(f"Bottom left text: {bottom_left_text}") if args.verbose else None
            print(f"Bottom rght text: {bottom_right_text}") if args.verbose else None
            print(f"Top left text: {top_left_text}") if args.verbose else None
            print(f"Top right text: {top_right_text}") if args.verbose else None

            # Since a detected word can contain the fencer's name, we need to use
            # regex to check this.
            if any(re.search(fencer_to_detect[0], word) for word in bottom_left_text) or \
                any(re.search(fencer_to_detect[1], word) for word in bottom_left_text):
                # Apply the red arrow overlay to the video file
                apply_overlay("red", video_file)
                fencer_detected = True
            if any(re.search(fencer_to_detect[0], word) for word in bottom_right_text) or \
                any(re.search(fencer_to_detect[1], word) for word in bottom_right_text):
                # Apply the green arrow overlay to the video file
                apply_overlay("green", video_file)
                fencer_detected = True
            if any(re.search(fencer_to_detect[0], word) for word in top_left_text) or \
                any(re.search(fencer_to_detect[1], word) for word in top_left_text):
                # Apply the red arrow overlay to the video file
                apply_overlay("red", video_file)
                fencer_detected = True
            if any(re.search(fencer_to_detect[0], word) for word in top_right_text) or \
                any(re.search(fencer_to_detect[1], word) for word in top_right_text):
                # Apply the green arrow overlay to the video file
                apply_overlay("green", video_file)
                fencer_detected = True

            # Draw the bounding boxes on the left and right sides of the frame
            cv2.rectangle(frame, (bottom_left_x, bottom_left_y), (bottom_left_x+bottom_left_w, bottom_left_y+bottom_left_h), left_box_color, 2)
            cv2.rectangle(frame, (bottom_right_x, bottom_right_y), (bottom_right_x+bottom_right_w, bottom_right_y+bottom_right_h), right_box_color, 2)
            cv2.rectangle(frame, (top_left_x, top_left_y), (top_left_x+top_left_w, top_left_y+top_left_h), left_box_color, 2)
            cv2.rectangle(frame, (top_right_x, top_right_y), (top_right_x+top_right_w, top_right_y+top_right_h), right_box_color, 2)
            cv2.imshow('frame', frame)

            # Wait for a key press to exit
            if cv2.waitKey(25) & 0xFF == ord('q'):
                break

            # If the fencer is detected, break the loop
            if fencer_detected:
                break

        # Release the video capture and destroy all windows
        cap.release()
        cv2.destroyAllWindows()
