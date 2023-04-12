#!/usr/bin/env python

import cv2, pytesseract, ffmpeg, os, sys, argparse, re

def apply_overlay(side, video_file):
    # To keep the input and output files organized,
    # we will create an 'out' directory if it does not exist already.
    if not os.path.exists("out"):
        os.makedirs("out")

    input_file = video_file

    # Extract file extension from video file.
    file_extension = os.path.splitext(video_file)[1]

    # Create output file name. We will use the same name as the input file,
    # but replace the file extension with '.out' + file_extension.
    output_file = os.path.join("out", os.path.basename(video_file).replace(file_extension, ".out" + file_extension))

    # The side of the fencer is determined by the color of the bounding box.
    overlay_file = f"assets/arrows/{side}.png"

    input_stream = ffmpeg.input(input_file)
    overlay_stream = ffmpeg.input(overlay_file)

    # We want to overlay the arrow image in the center of the frame, 20 pixels
    # from the top. To do this, we will use the 'overlay' filter.
    # The 'x' and 'y' parameters are used to specify the position of the overlay.
    output = ffmpeg.filter([input_stream.video, overlay_stream], 'overlay', x='(W-w)/2', y='20')

    ffmpeg.output(output, output_file).overwrite_output().run()

if __name__ == "__main__":
    # Set the path to the Tesseract executable.
    pytesseract.pytesseract.tesseract_cmd = r"/usr/bin/tesseract"

    # Since we are expecting two arguments, we will use the argparse module
    # to parse the command line arguments.
    # The '--video' may contain multiple values, this is not the case for
    # the '--name' argument. We expect the fencer name to be a single string surrounded
    # by quotes, e.g. "Max Heinzer".
    parser = argparse.ArgumentParser(description='FFWF - Find Fencer Within Frame')
    parser.add_argument('--video', nargs='+', help='video file(s)', required=True)
    parser.add_argument('--name', type=str, help='fencer name(s)', required=True)
    parser.add_argument('--verbose', action='store_true', help='debug mode')

    args = parser.parse_args()

    video_files = args.video
    fencer_to_detect = args.name.split(' ')

    # Convert the fencer name to lowercase, since this is easier to compare
    # with the text extracted from the video frames.
    fencer_to_detect = [name.lower() for name in fencer_to_detect]

    print(f"Video files: {video_files}")
    print(f"Fencer to detect: {fencer_to_detect}")

    for video_file in video_files:
        # Load the video file
        try:
            cap = cv2.VideoCapture(video_file)
        except:
            print(f"Error: Could not load the video file '{video_file}'.", file=sys.stderr)
            sys.exit(1)

        # The script assumes that the fencer's name is typically displayed at the bottom of the frame.
        # Therefore, the bottom area of the frame is set as the default region of interest (ROI).
        # To further facilitate the detection of the fencer's side, the ROI is divided into two halves,
        # representing the left (red) and right (green) sides.
        # The size of the ROI is determined based on the width and height of the frame.
        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        bottom_left_x, bottom_left_y, bottom_left_w, bottom_left_h = 0, frame_height - frame_height//4, frame_width//2, frame_height
        bottom_right_x, bottom_right_y, bottom_right_w, bottom_right_h = frame_width//2, frame_height - frame_height//4, frame_width, frame_height

        # # For some clips from The Fencing Database (www.fencingdatabase.com/), the
        # fencer's name is displayed in the top left corner of the video. Therefore,
        # we also define this area of the frame as our region of interest (ROI). We
        # will (again) use the frame width and height to determine the size of the ROI.
        top_left_x, top_left_y, top_left_w, top_left_h = 0, 0, frame_width//10, frame_height//4
        top_right_x, top_right_y, top_right_w, top_right_h = frame_width//10, 0, frame_width//10, frame_height//4

        # We want to make it easier to visualize the bounding boxes on the video frames,
        # so we will assign different colors to the left and right sides of the fencer.
        # Consistent with the tradition in fencing, we will use red for the left
        # and green for the right side of the fencer.
        left_box_color = (0, 0, 255)  # Red
        right_box_color = (0, 255, 0) # Green

        # We want to exit the loop as soon as the fencer is detected, to move
        # on to the next video file. To do this, we will use a variable to keep
        # track of whether the fencer has been detected or not. If the variable
        # remains False after scanning all the frames, it means the fencer was not
        # found in the video.
        fencer_detected = False

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            # Since we want four bounding boxes, two for the left side and
            # two for the right side, we need to crop the left and right.
            # Here we store the bounding boxes in four separate variables,
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

            # Since OpenCV may not detect the fencer's full name in every frame,
            # we need to check if either the first or last name is present in the
            # text. If we find either of these names, we can assume that the fencer
            # is present in the frame. To do this, we will split the detected text
            # into individual words and check if the first or last name is present.
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
                apply_overlay("red", video_file)
                fencer_detected = True
            if any(re.search(fencer_to_detect[0], word) for word in bottom_right_text) or \
                any(re.search(fencer_to_detect[1], word) for word in bottom_right_text):
                apply_overlay("green", video_file)
                fencer_detected = True
            if any(re.search(fencer_to_detect[0], word) for word in top_left_text) or \
                any(re.search(fencer_to_detect[1], word) for word in top_left_text):
                apply_overlay("red", video_file)
                fencer_detected = True
            if any(re.search(fencer_to_detect[0], word) for word in top_right_text) or \
                any(re.search(fencer_to_detect[1], word) for word in top_right_text):
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
