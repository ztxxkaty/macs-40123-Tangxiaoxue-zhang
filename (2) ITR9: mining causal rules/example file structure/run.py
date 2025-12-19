# File name is :: run.py
import json, uuid, time, requests, websocket, urllib.parse, os, random, shutil
from PIL import Image
from io import BytesIO

# Parameters
COMFY = "http://127.0.0.1:8188"
WS = "ws://127.0.0.1:8188/ws"
txt_path = "macs-40123-ztxxkaty/data/pairs.txt"
pic_path = "ComfyUI/input/things_images"
output_path = "resmem/Pictures"
with open(txt_path) as f:
    pairs_lst = f.readlines()

def process_prompt(prompt):
    '''
    Porcess the prompt:
    (1) queue prompt
    (2) watch progress via websocket until done
    (3) pull history

    Inputs: prompt(json)
    Returns: hist(json), outputs(string)
    '''
    # queue prompt
    client_id = str(uuid.uuid4())
    r = requests.post(f"{COMFY}/prompt", json={"prompt": prompt, "client_id": client_id})
    r.raise_for_status()
    prompt_id = r.json()["prompt_id"]
    print("Queued prompt_id:", prompt_id)

    # Watch progress via websocket until done
    ws = websocket.WebSocket()
    ws.connect(f"{WS}?clientId={urllib.parse.quote(client_id)}")
    done = False
    while not done:
        msg = ws.recv()
        if isinstance(msg, bytes):
            continue
        data = json.loads(msg)
        if data.get("type") == "executing":
            # When node is None, the whole graph finished
            if data["data"].get("node") is None and data["data"].get("prompt_id") == prompt_id:
                done = True
    ws.close()
    print("Execution finished.")

    # pull history
    hist = requests.get(f"{COMFY}/history/{prompt_id}").json()
    outputs = hist[prompt_id]["outputs"]
    return hist, outputs

def clear_output(target_dir):
    if os.path.exists(target_dir):
        shutil.rmtree(target_dir)   # deletes the whole folder
        print("Deleted:", target_dir)
    else:
        print("Nothing to delete — folder not found.")

# ---- Load prompt ----
with open("ComfyUI/workflows/2-pictures-combination.json", "r") as f:
    prompt = json.load(f)

for pair in pairs_lst:
    # ---- 1) get concepts ----
    pair_com = pair.split(", ")
    concept_1 = pair_com[0].replace(" ", "_")
    concept_2 = pair_com[1][:-1].replace(" ", "_")
    output_folder = os.path.join(output_path, concept_1+"+"+concept_2)
    os.makedirs(output_folder, exist_ok=True)

    # ---- 2) randomize the pairs ----
    concept_1_lst = os.listdir(os.path.join(pic_path, concept_1))
    concept_2_lst = os.listdir(os.path.join(pic_path, concept_2))
    random.shuffle(concept_1_lst)
    random.shuffle(concept_2_lst)
    cal = min(len(concept_1_lst), len(concept_2_lst))

    # ---- 3) loop: for each pair ----
    for i in range(cal):
        # image 1
        prompt["10"]["inputs"]["image"] = "things_images/" + concept_1 + "/" + concept_1_lst[i]
        # image 2
        prompt["12"]["inputs"]["image"] = "things_images/" + concept_2 + "/" + concept_2_lst[i]
        # filename_prefix
        prompt["19"]["inputs"]["filename_prefix"] = concept_1_lst[i][:-4] + "&&" + concept_2_lst[i][:-4]
        # prompt
        prompt["5"]["inputs"]["prompt"] = f"Combining image1 and image2 together naturally, which means combing {concept_1} and {concept_2} together naturally."

        # process the prompt and save the images ----
        hist, outputs = process_prompt(prompt)
        for node_id, out in outputs.items():
            if "images" not in out:
                continue
            for img in out["images"]:
                filename = img["filename"]
                subfolder = img.get("subfolder", "")
                ftype = img.get("type", "output")

                view_url = f"{COMFY}/view?filename={urllib.parse.quote(filename)}&subfolder={urllib.parse.quote(subfolder)}&type={ftype}"
                img_bytes = requests.get(view_url).content
                im = Image.open(BytesIO(img_bytes))

                # save the photos
                save_path = os.path.join(output_folder, filename)
                im.save(save_path)
                print("Saved:", save_path,"\n")

                # delete the photos in the previous folder
                time.sleep(2)
                os.remove(os.path.join("ComfyUI/output", filename))