from flask import Flask, request
import sys
import traceback

# This is an example that uses the websockets api and the SaveImageWebsocket node to get images directly without
# them being saved to disk

import websocket  # NOTE: websocket-client (https://github.com/websocket-client/websocket-client)
import uuid
import json
import urllib.request
import urllib.parse
import base64

# set your server address here
server_address = ""
client_id = str(uuid.uuid4())

app = Flask(__name__)


@app.route("/", methods=["POST"])
def handler():
    for k, v in request.headers.items():
        if k.startswith("HTTP_"):
            # process custom request headers
            pass

    request_body = request.data
    request_method = request.method
    path_info = request.path
    content_type = request.content_type
    query_string = request.query_string.decode("utf-8")

    # print("request_body: {}".format(request_body))
    # print(
    #     "method: {} path: {} query_string: {}".format(
    #         request_method, path_info, query_string
    #     )
    # )
    body = json.loads(request_body)

    # do something here
    try :
        prompt_text = body["prompt"]
        node_id = body["node_id"]

        prompt = json.loads(prompt_text)

        ws = websocket.WebSocket()
        ws.connect("ws://{}/ws?clientId={}".format(server_address, client_id))
        images = get_images(ws, prompt)
        output_images = images[node_id]
    except Exception as e:
        return traceback.format_exception_only(type(e), e)[0], 400, {"Content-Type": "text/plain"}

    sys.stdout.flush()
    return render(output_images), 200, {"Content-Type": "application/json"}

def render(data):
    result_dict = {}
    result_dict["code"] = "SUCCESS"
    result_dict["msg"] = "success"
    result_dict["data"] = data
    return json.dumps(result_dict)


def queue_prompt(prompt):
    p = {"prompt": prompt, "client_id": client_id}
    data = json.dumps(p).encode("utf-8")
    req = urllib.request.Request("http://{}/prompt".format(server_address), data=data)
    return json.loads(urllib.request.urlopen(req).read())


def get_image(filename, subfolder, folder_type):
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    with urllib.request.urlopen(
        "http://{}/view?{}".format(server_address, url_values)
    ) as response:
        return response.read()


def get_history(prompt_id):
    with urllib.request.urlopen(
        "http://{}/history/{}".format(server_address, prompt_id)
    ) as response:
        return json.loads(response.read())


def get_images(ws, prompt):
    prompt_id = queue_prompt(prompt)["prompt_id"]
    output_images = {}
    while True:
        out = ws.recv()
        # print("Output: " + str(out))
        if isinstance(out, str):
            message = json.loads(out)
            if message["type"] == "executing":
                data = message["data"]
                if data["node"] is None and data["prompt_id"] == prompt_id:
                    break  # Execution is done
        else:
            continue  # previews are binary data

    history = get_history(prompt_id)[prompt_id]
    # print("history: " + str(history))
    for o in history["outputs"]:
        for node_id in history["outputs"]:
            node_output = history["outputs"][node_id]
            if "images" in node_output:
                images_output = []
                for image in node_output["images"]:
                    image_data = get_image(
                        image["filename"], image["subfolder"], image["type"]
                    )
                    # 将二进制数据编码为 base64
                    base64_data = base64.b64encode(image_data)

                    # 将 base64 数据转换为字符串（如果需要）
                    base64_string = base64_data.decode('utf-8')
                    images_output.append(base64_string)
                output_images[node_id] = images_output

    return output_images

# Commented out code to display the output images:

# for node_id in images:
#     for image_data in images[node_id]:
#         from PIL import Image
#         import io
#         image = Image.open(io.BytesIO(image_data))
#         image.show()

if __name__ == "__main__":
    app.run()
