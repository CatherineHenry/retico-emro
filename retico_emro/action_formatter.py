import re

import cozmo
from PIL import Image
from cozmo import exceptions
from cozmo.util import degrees, Angle

import retico_core
from retico_core import abstract, UpdateType
from retico_core.text import TextIU
from retico_gred.gred_module import GREDTextIU


class ActionExecutionModule(abstract.AbstractModule):
    @staticmethod
    def name():
        return "Action Execution Module"
    @staticmethod
    def description():
        return "Execute GRED‐generated actions on the robot."
    @staticmethod
    def input_ius():
        return [GREDTextIU]

    @staticmethod
    def output_iu():
        return TextIU

    def __init__(self, robot, **kwargs):
        super().__init__(**kwargs)
        self.robot = robot

    def execute(self, actions_str):
        # strip out any leftover model markers
        # actions_str is like "set_volume_30 say_text_Hi! move_head_0_-10_0_80 ..."
        # split on spaces following a number, otherwise we have erroneous split on some "say text" that has a space in it
        for token in re.split(r'(?<=\d)\s+', actions_str):
            if token.startswith("say_text_"):
                rest = token[len("say_text_"):]
                parts = rest.split("_")
                sentence = parts[0]
                # duration = ""
                # for part in parts:
                #     if part.isdigit():
                #         duration+=part
                #     else:
                #         sentence+=part
                # # self.robot.set_robot_volume(1)

                sentence = "aawwhn" if sentence == "yawn" else sentence
                # self.robot.say_text(text=sentence, duration_scalar=int(duration), in_parallel=True)
                self.robot.say_text(text=sentence, in_parallel=True).wait_for_completed()
                # self.robot.say_text(text=sentence, duration_scalar=int(duration)).wait_for_completed()
                # self.robot.set_robot_volume(0)
                continue

            # handle display_face_ tokens → change_image('X.png', timeout)
            if token.startswith("display_oled_face_"):
                # only keep last two parts: image base + timeout, add “.png”
                rest = token[len("display_oled_face_image"):]
                parts = rest.split("_")
                image_base = parts[-2]
                timeout    = parts[-1]
                try:
                    face_image = Image.open(f"../../retico-emro/cozmo_faces/{image_base}.png")
                except FileNotFoundError:
                    print(f"Could not find face file {image_base}. Continuing without setting face.")
                    continue
                # resize to fit on Cozmo's face screen
                face_image = face_image.resize(cozmo.oled_face.dimensions(), Image.BICUBIC)
                # convert the image to the format used by the oled screen
                face_image = cozmo.oled_face.convert_image_to_screen_data(face_image, invert_image=False)
                # dispatch to robot
                try:
                    self.robot.display_oled_face_image(face_image, duration_ms=float(timeout) * 1000.0, in_parallel=True)
                except exceptions.RobotBusy:
                    print("Already have a face in action. Continuing execution.")
                continue


            if token.startswith("turn_in_place_"):
                rest = token[len("turn_in_place_"):]
                parts = rest.split("_")
                angle = degrees(int(parts[-2]))
                speed = Angle(int(parts[-1]))
                self.robot.turn_in_place(angle, accel=speed, in_parallel=True)
                continue

            if token.startswith("set_lift_height_"):
                rest = token[len("set_lift_height"):]
                parts = rest.split("_")
                height = float(parts[-2])
                speed = float(parts[-1])
                self.robot.set_lift_height(height, duration=speed, in_parallel=True).wait_for_completed()
                continue


            if token.startswith("drive_straight_"):
                continue
                # I don't want drive straight behaviour, so leaving updating this to work with Cozmo for later

            parts = token.split("_")
            name = parts[0]
            arg_parts = parts[1:]
            # check if first i segments form a valid robot method
            for i in range(len(parts)):
                multi_part = "_".join(parts[:i])
                if hasattr(self.robot, multi_part):
                    name = multi_part
                    arg_parts = parts[i:]

            # convert args: try int(), else keep as string
            args = []
            for a in arg_parts:
                if a.isdigit():
                    args.append(int(a))
                else:
                    try: # not all values are ints, some are floats. isdigit does not catch float strings and isdecimal didn't either
                        args.append(float(a))
                    except ValueError:
                        args.append(a)

            # dispatch to robot
            getattr(self.robot, name)(*args)

        # reset lift height to 0 so it doesn't interfere with the camera
        self.robot.set_lift_height(0.0, in_parallel=True).wait_for_completed()

    def process_update(self, update_message):
        # for every ADD update carry the payload into execute()
        for iu, typ in update_message:
            if typ == UpdateType.ADD:
                print(f"Executing action IU: {iu}")
                self.execute(iu.payload)

                # prepare result update
                output_iu = self.create_iu(iu)
                output_iu.payload = "Emotion Actions Complete" # Have an output so we can verify the actions executed before continuing to next Module

                return retico_core.UpdateMessage.from_iu(output_iu, retico_core.UpdateType.ADD)

