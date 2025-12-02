import os, json, threading, time, platform
import models as md
import tkinter as tk
import importlib, servo
from tkinter import ttk, font, messagebox
from tkinter.scrolledtext import ScrolledText
from LEDLight import StatusLED

if __name__ != "__main__":
    class _Dummy:
        def __init__(self, *a, **k): pass
        def insert(self, *a, **k):
            text = a[-1] if a else k.get("text", "")
            if text is not None:
                print(text, end="" if text.endswith("\n") else "\n")
        def delete(self, *a, **k): pass
        def see(self, *a, **k): pass
        def update_idletasks(self, *a, **k): pass
        def yview(self, *a, **k): pass
        def yview_moveto(self, *a, **k): pass
        def tag_config(self, *a, **k): pass
        def tag_add(self, *a, **k): pass
        def mark_set(self, *a, **k): pass
        def index(self, *a, **k): return "end"
        def set(self, *a, **k): pass
        def get(self, *a, **k): return ""
        def after(self, *a, **k): pass
        def after_cancel(self, *a, **k): pass
        def config(self, *a, **k): pass
        def configure(self, *a, **k): pass
        def start_blink(self): pass
        def stop_blink(self): pass
        def clipboard_clear(self): pass
    dummy = _Dummy()
    for name in [
        "scheduler",
        "dropdown", "branch_dropdown",
        "entry_version", "entry_note",
        "build_android_test_button", "build_android_public_button", "build_android_both_button",
        "btn_android", "btn_ios", "btn_both", "btn_all",
        "checkbox_upload_unity_cloud_var",
        "update_player_prefs_button", "grade_resolve_button", "clean_build_button",
        "build_all_button", "build_all_public_button",
        "selected_option", "env_label_var", "bucket_id_var",
        "build_time_var", "build_time_history", "output_text", "led", "clipboard_clear"
    ]:
        globals()[name] = dummy
    def state_ui(state): pass
    def clear_build_time_history(): pass
    def start_live_timer(label): pass
    def stop_live_timer(label): pass

    import tkinter.messagebox as _mb
    def _si(t,m,**k): print(f"[INFO] {t}: {m}")
    def _sw(t,m,**k): print(f"[WARN] {t}: {m}")
    def _se(t,m,**k): print(f"[ERR]  {t}: {m}")
    _mb.showinfo = _si
    _mb.showwarning = _sw
    _mb.showerror = _se

payload_path = "servo-config.json"
if not os.path.isfile(payload_path):
    with open(payload_path, "w") as f:
        json.dump({}, f, indent=2)
with open(payload_path, "r") as f:
    pure_servo_config_payload = json.load(f)
servo_config_payload = json.dumps(pure_servo_config_payload, indent=2)
initial_env = pure_servo_config_payload["target_environment"]["environment"]

unity_path = ""
ccd_path = ""
project_path = ""
cryptic_file = ""
unity_cloud_username = "7b76f4b6-1f32-4635-8443-b935c3b0a6e3"
unity_cloud_api_key = "qV1F65CUwZhnJ6NibrmND8BZjt_DIaxS"
project_id = "33d3ac8f-0923-418a-9588-526309b56a92"
orgs_id = "18966922554057"
# Notes:
# QA
# Production
# Staging
# Development
env_bucket_id = {
    "env_id": [
        "7c9b7696-78b1-41a8-9143-9b86f0519e10", # QA
        "c5df4fe6-91f6-48dd-b0fe-9f0f78b33384", # Production
        "c8bdd6b3-a88c-4cef-a261-6d4376d91c9e", # Staging
        "edea636c-6f6f-44e0-a63b-6f78379c6f78", # Development
    ],
    "bucket_id": [
        "5d5e31cb-3b6e-4bb8-8af3-df215b983453", # QA
        "d1b05e98-2ef0-461c-a391-94577c836dd3", # Production
        "507c0977-7147-4ec0-9f53-5033cec78985", # Staging
        "654d06bb-54ff-4a6e-b2c3-6914d3fceb4f", # Development
    ]
}
cdc_path = {
    "paths": []
}
keystore_paths_pass = {
    "PATHS": {},
    "PASS": {
        "QA_KEYSTORE_PASS": "",
        "PRODUCTION_KEYSTORE_PASS": "",
        "STAGING_KEYSTORE_PASS": "",
        "DEVELOP_KEYSTORE_PASS": "",
    }
}
env_name_map = {
    "QA_ENV": "7c9b7696-78b1-41a8-9143-9b86f0519e10",
    "PRODUCTION_ENV": "c5df4fe6-91f6-48dd-b0fe-9f0f78b33384",
    "STAGING_ENV": "c8bdd6b3-a88c-4cef-a261-6d4376d91c9e",
    "DEVELOP_ENV": "edea636c-6f6f-44e0-a63b-6f78379c6f78",
}
bucket_name_map = {
    "QA_ENV": "5d5e31cb-3b6e-4bb8-8af3-df215b983453",
    "PRODUCTION_ENV": "d1b05e98-2ef0-461c-a391-94577c836dd3",
    "STAGING_ENV": "507c0977-7147-4ec0-9f53-5033cec78985",
    "DEVELOP_ENV": "654d06bb-54ff-4a6e-b2c3-6914d3fceb4f",
}

if platform.system() == "Windows":
    unity_path = r"C:\Program Files\Unity\Hub\Editor\2022.3.62f2\Editor\Unity.exe"
    ccd_path = r"C:\Users\User\Desktop\Project Folder\changokushi-heroes-client\CCDBuildData"
    project_path = r"C:\Users\User\Desktop\Project Folder\changokushi-heroes-client"
    paths = [
        r"..\Secured-Keys-QA\ch-ks-qa-upload.keystore",                 # QA
        r"..\Secured-Keys-Production\ch-ks-production-upload.keystore", # Production
        r"..\Secured-Keys-Staging\ch-ks-staging-upload.keystore",       # Staging
        r"..\Secured-Keys-Dev\ch-ks-dev-upload.keystore",               # Development
    ]
    cdc_path["paths"] = paths
    PATHS = {
        "QA_KEYSTORE_PATH": r"C:\cdc-custom\Secured-Keys-QA\ch-ks-qa-upload.keystore",
        "PRODUCTION_KEYSTORE_PATH": r"C:\cdc-custom\Secured-Keys-Production\ch-ks-production-upload.keystore",
        "STAGING_KEYSTORE_PATH": r"C:\cdc-custom\Secured-Keys-Staging\ch-ks-staging-upload.keystore",
        "DEVELOP_KEYSTORE_PATH": r"C:\cdc-custom\Secured-Keys-Dev\ch-ks-dev-upload.keystore",
    }
    keystore_paths_pass["PATHS"] = PATHS
elif platform.system() == "Darwin":
    unity_path = "/Applications/Unity/Hub/Editor/2022.3.62f2/Unity.app/Contents/MacOS/Unity"
    #unity_path = "/Applications/Unity/Hub/Editor/2022.3.62f2-x86_64/Unity.app/Contents/MacOS/Unity"
    ccd_path = "/Users/dreamteamadmin/Projects/changokushi-heroes-client/CCDBuildData"
    project_path = "/Users/dreamteamadmin/Projects/changokushi-heroes-client"
    paths = []
    cdc_path["paths"] = paths
    PATHS = {
        "QA_KEYSTORE_PATH": "/Users/dreamteamadmin/Projects/keystore/QA/Secured-Keys-QA/ch-ks-qa-upload.keystore",
        "PRODUCTION_KEYSTORE_PATH": "/Users/dreamteamadmin/Projects/keystore/Production/Secured-Keys-Production/ch-ks-production-upload.keystore",
        "STAGING_KEYSTORE_PATH": "/Users/dreamteamadmin/Projects/keystore/Staging/Secured-Keys-Staging/ch-ks-staging-upload.keystore",
        "DEVELOP_KEYSTORE_PATH": "/Users/dreamteamadmin/Projects/keystore/Develop/Secured-Keys-Dev/ch-ks-dev-upload.keystore",
    }
    keystore_paths_pass["PATHS"] = PATHS

script_dir = os.path.dirname(os.path.abspath(__file__))
cryptic_file = os.path.join(script_dir, "cryptic", "keystore.txt")
env_bucket_id_payload = json.dumps(env_bucket_id)
key = "lLQn6qHOcek7Qs3LJKl9yC_POVko88thaLt5O0FUqdw="
keystores = md.decrypt_file_lines_in_place(cryptic_file, key)
keystore_pass_keys = [
    "QA_KEYSTORE_PASS",
    "PRODUCTION_KEYSTORE_PASS",
    "STAGING_KEYSTORE_PASS",
    "DEVELOP_KEYSTORE_PASS",
]
new_pass_dict = {
    key: keystores[i].strip()
    for i, key in enumerate(keystore_pass_keys)
}
keystore_paths_pass["PASS"] = new_pass_dict

def state_ui(state):
    def _apply():
        if dropdown is None:
            return
        if state == "normal":
            dropdown.config(state="readonly")
        entry_version.config(state=state)
        entry_note.config(state=state)
        build_android_test_button.config(state=state)
        build_android_public_button.config(state=state)
        build_android_both_button.config(state=state)
        btn_android.config(state=state)
        btn_ios.config(state=state)
        btn_both.config(state=state)
        btn_all.config(state=state)
        checkbox_upload_unity_cloud.config(state=state)
        update_player_prefs_button.config(state=state)
        grade_resolve_button.config(state=state)
        clean_build_button.config(state=state)
        build_all_button.config(state=state)
        build_all_public_button.config(state=state)
        build_android_button.config(state=state)
        build_iOS_button.config(state=state)
        build_backup_button.config(state=state)
        git_checkout_branch_button.config(state=state)
        btn_sign_off.config(state=state)
        btn_snapshot.config(state=state)
    if scheduler:
        scheduler.after(0, _apply)
    else:
        _apply()

def clear_output_text():
    output_text.after(0, stop_live_timer, build_time_var)
    output_text.after(0, lambda: build_time_var.set(f"Build Time: ---"))
    output_text.after(0, state_ui, "normal")

def on_remote_public_build(env=None, version=None, note=None):
    clear_build_time_history()
    if version is None and entry_version is not None:
        version = entry_version.get()
    if note is None and entry_note is not None:
        note    = entry_note.get()
    if env is None:
        env = selected_option.get()
    push_to_cloud = (str(checkbox_upload_unity_cloud_var.get()) if checkbox_upload_unity_cloud_var is not None else "False")
    steps = [
        ("Check git lfs", lambda: md.check_git_lfs(output_text, project_path)),
        ("Remove Orphan .meta", lambda: md.remove_orphan_meta_files(output_text, project_path)),
        ("Build Android", lambda: md.remote_public_build_android(
            output_text,
            build_time_history,
            unity_path,
            project_path,
            env,
            version,
            note,
            push_to_cloud,
            unity_cloud_api_key,
            orgs_id,
            project_id,
            env_bucket_id_payload,
            keystore_paths_pass,
            led
        )),
        ("Build iOS", lambda: md.remote_public_build_ios(
            output_text,
            build_time_history,
            unity_path,
            project_path,
            env,
            version,
            note,
            push_to_cloud,
            unity_cloud_api_key,
            orgs_id,
            project_id,
            env_bucket_id_payload,
            keystore_paths_pass,
            led
        )),
    ]
    state_ui("disabled")
    build_time_var.set("Build Time: --")
    start_live_timer(build_time_var)
    start_time = time.perf_counter()
    def run_build():
        try:
            md.sequencing_actions(output_text, steps)
            copy_build_time_history()
        finally:
            output_text.after(0, stop_live_timer, build_time_var)
            elapsed = time.perf_counter() - start_time
            output_text.after(0, lambda: build_time_var.set(f"Build Time: {elapsed:.2f}s"))
            output_text.after(0, state_ui, "normal")
    threading.Thread(target=run_build, daemon=True).start()

def on_remote_public_build_android(env=None, version=None, note=None):
    version = entry_version.get() if version is None else version
    note    = entry_note.get() if note is None else note
    push_to_cloud = (str(checkbox_upload_unity_cloud_var.get()) if checkbox_upload_unity_cloud_var is not None else "False")
    if env is None:
        env_id = selected_option.get()
    else:
        env_id = env
    def run_build():
        state_ui("disabled")
        build_time_var.set("Build Time: --")
        start_live_timer(build_time_var)
        start_time = time.perf_counter()
        md.remote_public_build_android(
            output_text,
            build_time_history,
            unity_path,
            project_path,
            env_id,
            version,
            note,
            push_to_cloud,
            unity_cloud_api_key,
            orgs_id,
            project_id,
            env_bucket_id_payload,
            keystore_paths_pass,
            led
        )
        end_time = time.perf_counter()
        stop_live_timer(build_time_var)
        elapsed = end_time - start_time
        build_time_var.set(f"Build Time: {elapsed:.2f}s")
        state_ui("normal")
    threading.Thread(target=run_build).start()

def on_remote_public_build_ios(env=None, version=None, note=None):
    version = entry_version.get() if version is None else version
    note    = entry_note.get() if note is None else note
    push_to_cloud = (str(checkbox_upload_unity_cloud_var.get()) if checkbox_upload_unity_cloud_var is not None else "False")
    if env is None:
        env_id = selected_option.get()
    else:
        env_id = env
    def run_build():
        state_ui("disabled")
        build_time_var.set("Build Time: --")
        start_live_timer(build_time_var)
        start_time = time.perf_counter()
        md.remote_public_build_ios(
            output_text,
            build_time_history,
            unity_path,
            project_path,
            env_id,
            version,
            note,
            push_to_cloud,
            unity_cloud_api_key,
            orgs_id,
            project_id,
            env_bucket_id_payload,
            keystore_paths_pass,
            led
        )
        end_time = time.perf_counter()
        stop_live_timer(build_time_var)
        elapsed = end_time - start_time
        build_time_var.set(f"Build Time: {elapsed:.2f}s")
        state_ui("normal")
    threading.Thread(target=run_build).start()

def on_remote_test_build(env=None, version=None, note=None):
    version = entry_version.get() if version is None else version
    note    = entry_note.get() if note is None else note
    push_to_cloud = (str(checkbox_upload_unity_cloud_var.get())
                     if checkbox_upload_unity_cloud_var is not None else "False")
    if env is None:
        env_id = selected_option.get()
    else:
        env_id = env
    def run_build():
        state_ui("disabled")
        build_time_var.set("Build Time: --")
        start_live_timer(build_time_var)
        start_time = time.perf_counter()
        md.remote_test_build(
            output_text,
            build_time_history,
            unity_path,
            project_path,
            env_id,
            version,
            note,
            push_to_cloud,
            unity_cloud_api_key,
            orgs_id,
            project_id,
            env_bucket_id_payload,
            keystore_paths_pass,
            led
        )
        end_time = time.perf_counter()
        stop_live_timer(build_time_var)
        elapsed = end_time - start_time
        build_time_var.set(f"Build Time: {elapsed:.2f}s")
        state_ui("normal")
    threading.Thread(target=run_build).start()

def on_remote_both_build(env=None, version=None, note=None):
    version = entry_version.get() if version is None else version
    note    = entry_note.get() if note is None else note
    push_to_cloud = (str(checkbox_upload_unity_cloud_var.get())
                     if checkbox_upload_unity_cloud_var is not None else "False")
    if env is None:
        env_id = selected_option.get()
    else:
        env_id = env
    def run_build():
        state_ui("disabled")
        build_time_var.set("Build Time: --")
        start_live_timer(build_time_var)
        start_time = time.perf_counter()
        md.remote_both_build(
            output_text,
            build_time_history,
            unity_path,
            project_path,
            env_id,
            version,
            note,
            push_to_cloud,
            unity_cloud_api_key,
            orgs_id,
            project_id,
            env_bucket_id_payload,
            keystore_paths_pass,
            led
        )
        end_time = time.perf_counter()
        stop_live_timer(build_time_var)
        elapsed = end_time - start_time
        build_time_var.set(f"Build Time: {elapsed:.2f}s")
        state_ui("normal")
    threading.Thread(target=run_build).start()

def on_build_addressable(version=None, env=None):
    if env is None:
        env = selected_option.get()
    if version is None and entry_version is not None:
        version = entry_version.get()
    bucket_id = md.get_bucket_id(env_bucket_id, env)
    md.delete_dirs_by_env_id(output_text, ccd_path, env_bucket_id, env)
    steps = [
        ("Clean and checkout Branch", lambda: (
            md.clear_local_changes(project_path, output_text),
            md.checkout_or_create_branch(output_text, project_path, version),
            branch_dropdown.set(md.get_current_branch(project_path))
        )),
        ("Copy and paste script", lambda: (
            md.copy_paste_scripting_builder_helper(project_path),
        )),
        ("Update App Title", lambda: md.change_correct_app_title(output_text, project_path, env)),
        ("Recompile Script", lambda: md.force_script_recompile(
            output_text, build_time_history,
            unity_path, project_path, led
        )),
        ("Switch Environment", lambda: md.remote_change_environment(
            output_text, build_time_history,
            unity_path, project_path,
            keystore_paths_pass,
            env,led
        )),
        ("Build Addressable Android", lambda: md.build_addressable_android(
            output_text,
            build_time_history,
            unity_path,
            project_path,
            version,
            ccd_path,
            env,
            project_id,
            bucket_id,
            led
        )),
        ("Build Addressable iOS", lambda: md.build_addressable_ios(
            output_text,
            build_time_history,
            unity_path,
            project_path,
            version,
            ccd_path,
            env,
            project_id,
            bucket_id,
            led
        )),
        ("Upload Android Addressable", lambda: md.upload_ccd_cli(
            output_text,
            project_path,
            unity_cloud_username,
            unity_cloud_api_key,
            project_id,
            env, ccd_path,
            entrie_name="Android",
            version=version,
            create_release=False,
        )),
        ("Upload iOS Addressable", lambda: md.upload_ccd_cli(
            output_text,
            project_path,
            unity_cloud_username,
            unity_cloud_api_key,
            project_id,
            env, ccd_path,
            entrie_name="iOS",
            version=version,
            create_release=True,
        )),
    ]
    state_ui("disabled")
    build_time_var.set("Build Time: --")
    start_live_timer(build_time_var)
    start_time = time.perf_counter()
    def run_build():
        try:
            md.sequencing_actions(output_text, steps)
        finally:
            output_text.after(0, stop_live_timer, build_time_var)
            elapsed = time.perf_counter() - start_time
            output_text.after(0, lambda: build_time_var.set(f"Build Time: {elapsed:.2f}s"))
            output_text.after(0, state_ui, "normal")
    threading.Thread(target=run_build, daemon=True).start()

def on_build_all_addressable(version=None, note=None):
    envs = ["DEVELOP_ENV", "QA_ENV", "STAGING_ENV", "PRODUCTION_ENV"]
    for env in envs:
        if version is None and entry_version is not None:
            version = entry_version.get()
        if note is None and entry_note is not None:
            note    = entry_note.get()
        bucket_id = md.get_bucket_id(env_bucket_id, env)
        md.delete_dirs_by_env_id(output_text, ccd_path, env_bucket_id, env)
        steps = [
            ("Clean and checkout Branch", lambda: (
                md.clear_local_changes(project_path, output_text),
                md.checkout_or_create_branch(output_text, project_path, version),
                branch_dropdown.set(md.get_current_branch(project_path))
            )),
            ("Copy and paste script", lambda: (
                md.copy_paste_scripting_builder_helper(project_path),
            )),
            ("Update App Title", lambda: md.change_correct_app_title(output_text, project_path, env)),
            ("Recompile Script", lambda: md.force_script_recompile(
                output_text, build_time_history,
                unity_path, project_path, led
            )),
            ("Switch Environment", lambda: md.remote_change_environment(
                output_text, build_time_history,
                unity_path, project_path,
                keystore_paths_pass,
                env,led
            )),
            ("Build Addressable Android", lambda: md.build_addressable_android(
                output_text,
                build_time_history,
                unity_path,
                project_path,
                version,
                ccd_path,
                env,
                project_id,
                bucket_id,
                led
            )),
            ("Build Addressable iOS", lambda: md.build_addressable_ios(
                output_text,
                build_time_history,
                unity_path,
                project_path,
                version,
                ccd_path,
                env,
                project_id,
                bucket_id,
                led
            )),
            ("Upload Android Addressable", lambda: md.upload_ccd_cli(
                output_text,
                project_path,
                unity_cloud_username,
                unity_cloud_api_key,
                project_id,
                env, ccd_path,
                entrie_name="Android",
                version=version,
                create_release=False,
            )),
            ("Upload iOS Addressable", lambda: md.upload_ccd_cli(
                output_text,
                project_path,
                unity_cloud_username,
                unity_cloud_api_key,
                project_id,
                env, ccd_path,
                entrie_name="iOS",
                version=version,
                create_release=True,
            )),
        ]
        state_ui("disabled")
        build_time_var.set("Build Time: --")
        start_live_timer(build_time_var)
        start_time = time.perf_counter()
        def run_build():
            try:
                md.sequencing_actions(output_text, steps)
            finally:
                output_text.after(0, stop_live_timer, build_time_var)
                elapsed = time.perf_counter() - start_time
                output_text.after(0, lambda: build_time_var.set(f"Build Time: {elapsed:.2f}s"))
                output_text.after(0, state_ui, "normal")
        threading.Thread(target=run_build, daemon=True).start()

def on_build_addressable_android(version=None, env=None):
    if env is None:
        env = selected_option.get()
    if version is None and entry_version is not None:
        version = entry_version.get()
    bucket_id = md.get_bucket_id(env_bucket_id, env)
    md.delete_dirs_by_env_id(output_text, ccd_path, env_bucket_id, env)
    steps = [
        ("Clean and checkout Branch", lambda: (
            md.clear_local_changes(project_path, output_text),
            md.checkout_or_create_branch(output_text, project_path, version),
            branch_dropdown.set(md.get_current_branch(project_path))
        )),
        ("Copy and paste script", lambda: (
            md.copy_paste_scripting_builder_helper(project_path),
        )),
        ("Update App Title", lambda: md.change_correct_app_title(output_text, project_path, env)),
        ("Recompile Script", lambda: md.force_script_recompile(
            output_text, build_time_history,
            unity_path, project_path, led
        )),
        ("Switch Environment", lambda: md.remote_change_environment(
            output_text, build_time_history,
            unity_path, project_path,
            keystore_paths_pass,
            env,led
        )),
        ("Build Addressable Android", lambda: md.build_addressable_android(
            output_text,
            build_time_history,
            unity_path,
            project_path,
            version,
            ccd_path,
            env,
            project_id,
            bucket_id,
            led
        )),
        ("Upload Android Addressable", lambda: md.upload_ccd_cli(
            output_text,
            project_path,
            unity_cloud_username,
            unity_cloud_api_key,
            project_id,
            env, ccd_path,
            entrie_name="Android",
            version=version,
            create_release=True,
        ))
    ]
    state_ui("disabled")
    build_time_var.set("Build Time: --")
    start_live_timer(build_time_var)
    start_time = time.perf_counter()
    def run_build():
        try:
            md.sequencing_actions(output_text, steps)
        finally:
            output_text.after(0, stop_live_timer, build_time_var)
            elapsed = time.perf_counter() - start_time
            output_text.after(0, lambda: build_time_var.set(f"Build Time: {elapsed:.2f}s"))
            output_text.after(0, state_ui, "normal")
    threading.Thread(target=run_build, daemon=True).start()


def on_build_addressable_ios(version=None, env=None):
    if env is None:
        env = selected_option.get()
    if version is None and entry_version is not None:
        version = entry_version.get()
    bucket_id = md.get_bucket_id(env_bucket_id, env)
    md.delete_dirs_by_env_id(output_text, ccd_path, env_bucket_id, env)
    steps = [
        ("Clean and checkout Branch", lambda: (
            md.clear_local_changes(project_path, output_text),
            md.checkout_or_create_branch(output_text, project_path, version),
            branch_dropdown.set(md.get_current_branch(project_path))
        )),
        ("Copy and paste script", lambda: (
            md.copy_paste_scripting_builder_helper(project_path),
        )),
        ("Update App Title", lambda: md.change_correct_app_title(output_text, project_path, env)),
        ("Recompile Script", lambda: md.force_script_recompile(
            output_text, build_time_history,
            unity_path, project_path, led
        )),
        ("Switch Environment", lambda: md.remote_change_environment(
            output_text, build_time_history,
            unity_path, project_path,
            keystore_paths_pass,
            env,led
        )),
        ("Build Addressable iOS", lambda: md.build_addressable_ios(
            output_text,
            build_time_history,
            unity_path,
            project_path,
            version,
            ccd_path,
            env,
            project_id,
            bucket_id,
            led
        )),
        ("Upload iOS Addressable", lambda: md.upload_ccd_cli(
            output_text,
            project_path,
            unity_cloud_username,
            unity_cloud_api_key,
            project_id,
            env, ccd_path,
            entrie_name="iOS",
            version=version,
            create_release=True,
        )),
    ]
    state_ui("disabled")
    build_time_var.set("Build Time: --")
    start_live_timer(build_time_var)
    start_time = time.perf_counter()
    def run_build():
        try:
            md.sequencing_actions(output_text, steps)
        finally:
            output_text.after(0, stop_live_timer, build_time_var)
            elapsed = time.perf_counter() - start_time
            output_text.after(0, lambda: build_time_var.set(f"Build Time: {elapsed:.2f}s"))
            output_text.after(0, state_ui, "normal")
    threading.Thread(target=run_build, daemon=True).start()
    
def on_patching_addressable(env=None):
    if env is None:
        env_id = selected_option.get()
    else:
        env_id = env
    md.delete_dirs_by_env_id(output_text, ccd_path, env_bucket_id, env_id)
    def run_build():
        state_ui("disabled")
        build_time_var.set("Build Time: --")
        start_live_timer(build_time_var)
        start_time = time.perf_counter()
        md.patching_addressable(
            output_text,
            build_time_history,
            unity_path,
            project_path,
            env_id,
            led
        )
        end_time = time.perf_counter()
        stop_live_timer(build_time_var)
        elapsed = end_time - start_time
        build_time_var.set(f"Build Time: {elapsed:.2f}s")
        state_ui("normal")
    threading.Thread(target=run_build).start()

def on_build_environment(env=None, version=None, note=None):
    clear_build_time_history()
    md.clear_console_log(output_text)
    if version is None and entry_version is not None:
        version = entry_version.get()
    if note is None and entry_note is not None:
        note    = entry_note.get()
    if env is None:
        env = selected_option.get()
    bucket_id = md.get_bucket_id(env_bucket_id, env)
    md.delete_dirs_by_env_id(output_text, ccd_path, env_bucket_id, env)
    steps = [
        ("Clean and checkout Branch", lambda: (
            md.clear_local_changes(project_path, output_text),
            md.checkout_or_create_branch(output_text, project_path, version),
            branch_dropdown.set(md.get_current_branch(project_path))
        )),
        ("Copy and paste script", lambda: (
            md.copy_paste_scripting_builder_helper(project_path),
        )),
        ("Update App Title", lambda: md.change_correct_app_title(output_text, project_path, env)),
        ("Recompile Script", lambda: md.force_script_recompile(
            output_text, build_time_history,
            unity_path, project_path, led
        )),
        ("Switch Environment", lambda: md.remote_change_environment(
            output_text, build_time_history,
            unity_path, project_path,
            keystore_paths_pass,
            env,led
        )),
        ("Build Addressable Android", lambda: md.build_addressable_android(
            output_text,
            build_time_history,
            unity_path,
            project_path,
            version,
            ccd_path,
            env,
            project_id,
            bucket_id,
            led
        )),
        ("Check git lfs", lambda: md.check_git_lfs(output_text, project_path)),
        ("Remove Orphan .meta", lambda: md.remove_orphan_meta_files(output_text, project_path)),
        ("Build Android", lambda: md.remote_public_build_android(
            output_text,
            build_time_history,
            unity_path,
            project_path,
            env,
            version,
            note,
            "False",
            unity_cloud_api_key,
            orgs_id,
            project_id,
            env_bucket_id_payload,
            keystore_paths_pass,
            led
        )),
        ("Build Addressable iOS", lambda: md.build_addressable_ios(
            output_text,
            build_time_history,
            unity_path,
            project_path,
            version,
            ccd_path,
            env,
            project_id,
            bucket_id,
            led
        )),
        ("Build iOS", lambda: md.remote_public_build_ios(
            output_text,
            build_time_history,
            unity_path,
            project_path,
            env,
            version,
            note,
             "False",
            unity_cloud_api_key,
            orgs_id,
            project_id,
            env_bucket_id_payload,
            keystore_paths_pass,
            led
        )),
        ("Upload Android Addressable", lambda: md.upload_ccd_cli(
            output_text,
            project_path,
            unity_cloud_username,
            unity_cloud_api_key,
            project_id,
            env, ccd_path,
            entrie_name="Android",
            version=version,
            create_release=False,
        )),
        ("Upload iOS Addressable", lambda: md.upload_ccd_cli(
            output_text,
            project_path,
            unity_cloud_username,
            unity_cloud_api_key,
            project_id,
            env, ccd_path,
            entrie_name="iOS",
            version=version,
            create_release=True,
        )),
    ]
    state_ui("disabled")
    build_time_var.set("Build Time: --")
    start_live_timer(build_time_var)
    start_time = time.perf_counter()
    def run_build():
        try:
            md.sequencing_actions(output_text, steps)
            android_build_version = int(md.get_version_code(env))
            ios_build_number = md.get_latest_build_number(env, version)
            servo.build_release_message_and_send(env, version, android_build_version, ios_build_number)
            copy_build_time_history()
        finally:
            output_text.after(0, stop_live_timer, build_time_var)
            elapsed = time.perf_counter() - start_time
            output_text.after(0, lambda: build_time_var.set(f"Build Time: {elapsed:.2f}s"))
            output_text.after(0, state_ui, "normal")
    threading.Thread(target=run_build, daemon=True).start()

def build_not_upload(env=None, version=None, note=None):
    clear_build_time_history()
    if version is None and entry_version is not None:
        version = entry_version.get()
    if note is None and entry_note is not None:
        note    = entry_note.get()
    if env is None:
        env = selected_option.get()
    bucket_id = md.get_bucket_id(env_bucket_id, env)
    md.delete_dirs_by_env_id(output_text, ccd_path, env_bucket_id, env)
    steps = [
        ("Clean and checkout Branch", lambda: (
            md.clear_local_changes(project_path, output_text),
            md.checkout_or_create_branch(output_text, project_path, version),
            branch_dropdown.set(md.get_current_branch(project_path))
        )),
        ("Copy and paste script", lambda: (
            md.copy_paste_scripting_builder_helper(project_path),
        )),
        ("Update App Title", lambda: md.change_correct_app_title(output_text, project_path, env)),
        ("Recompile Script", lambda: md.force_script_recompile(
            output_text, build_time_history,
            unity_path, project_path, led
        )),
        ("Switch Environment", lambda: md.remote_change_environment(
            output_text, build_time_history,
            unity_path, project_path,
            keystore_paths_pass,
            env,led
        )),
        ("Build Addressable Android", lambda: md.build_addressable_android(
            output_text,
            build_time_history,
            unity_path,
            project_path,
            version,
            ccd_path,
            env,
            project_id,
            bucket_id,
            led,
        )),
        ("Check git lfs", lambda: md.check_git_lfs(output_text, project_path)),
        ("Remove Orphan .meta", lambda: md.remove_orphan_meta_files(output_text, project_path)),
        ("Build Android", lambda: md.remote_public_build_android(
            output_text,
            build_time_history,
            unity_path,
            project_path,
            env,
            version,
            note,
            "False",
            unity_cloud_api_key,
            orgs_id,
            project_id,
            env_bucket_id_payload,
            keystore_paths_pass,
            led,
            upload=False
        )),
        ("Build Addressable iOS", lambda: md.build_addressable_ios(
            output_text,
            build_time_history,
            unity_path,
            project_path,
            version,
            ccd_path,
            env,
            project_id,
            bucket_id,
            led,
        )),
        ("Build iOS", lambda: md.remote_public_build_ios(
            output_text,
            build_time_history,
            unity_path,
            project_path,
            env,
            version,
            note,
            "False",
            unity_cloud_api_key,
            orgs_id,
            project_id,
            env_bucket_id_payload,
            keystore_paths_pass,
            led,
            upload=False
        ))
    ]
    state_ui("disabled")
    build_time_var.set("Build Time: --")
    start_live_timer(build_time_var)
    start_time = time.perf_counter()
    def run_build():
        try:
            md.sequencing_actions(output_text, steps)
            android_build_version = int(md.get_version_code(env))
            ios_build_number = md.get_latest_build_number(env, version)
            servo.build_release_message_and_send(env, version, android_build_version, ios_build_number)
            copy_build_time_history()
        finally:
            output_text.after(0, stop_live_timer, build_time_var)
            elapsed = time.perf_counter() - start_time
            output_text.after(0, lambda: build_time_var.set(f"Build Time: {elapsed:.2f}s"))
            output_text.after(0, state_ui, "normal")
    threading.Thread(target=run_build, daemon=True).start()

def on_build_environment_all(version=None, note=None):
    envs = ["DEVELOP_ENV", "QA_ENV", "STAGING_ENV", "PRODUCTION_ENV"]
    for env in envs:
        clear_build_time_history()
        if version is None and entry_version is not None:
            version = entry_version.get()
        if note is None and entry_note is not None:
            note    = entry_note.get()
        bucket_id = md.get_bucket_id(env_bucket_id, env)
        md.delete_dirs_by_env_id(output_text, ccd_path, env_bucket_id, env)
        steps = [
            ("Clean and checkout Branch", lambda: (
                md.clear_local_changes(project_path, output_text),
                md.checkout_or_create_branch(output_text, project_path, version),
                branch_dropdown.set(md.get_current_branch(project_path))
            )),
            ("Copy and paste script", lambda: (
                md.copy_paste_scripting_builder_helper(project_path),
            )),
            ("Update App Title", lambda: md.change_correct_app_title(output_text, project_path, env)),
            ("Recompile Script", lambda: md.force_script_recompile(
                output_text, build_time_history,
                unity_path, project_path, led
            )),
            ("Switch Environment", lambda: md.remote_change_environment(
                 output_text, build_time_history,
                 unity_path, project_path,
                 keystore_paths_pass,
                 env,led
             )),
            ("Build Addressable Android", lambda: md.build_addressable_android(
                output_text,
                build_time_history,
                unity_path,
                project_path,
                version,
                ccd_path,
                env,
                project_id,
                bucket_id,
                led
            )),
            ("Check git lfs", lambda: md.check_git_lfs(output_text, project_path)),
            ("Remove Orphan .meta", lambda: md.remove_orphan_meta_files(output_text, project_path)),
            ("Build Android", lambda: md.remote_public_build_android(
                output_text,
                build_time_history,
                unity_path,
                project_path,
                env,
                version,
                note,
                "False",
                unity_cloud_api_key,
                orgs_id,
                project_id,
                env_bucket_id_payload,
                keystore_paths_pass,
                led
            )),
            ("Build Addressable iOS", lambda: md.build_addressable_ios(
                output_text,
                build_time_history,
                unity_path,
                project_path,
                version,
                ccd_path,
                env,
                project_id,
                bucket_id,
                led
            )),
            ("Build iOS", lambda: md.remote_public_build_ios(
                output_text,
                build_time_history,
                unity_path,
                project_path,
                env,
                version,
                note,
                "False",
                unity_cloud_api_key,
                orgs_id,
                project_id,
                env_bucket_id_payload,
                keystore_paths_pass,
                led
            )),
            ("Upload Android Addressable", lambda: md.upload_ccd_cli(
                output_text,
                project_path,
                unity_cloud_username,
                unity_cloud_api_key,
                project_id,
                env, ccd_path,
                entrie_name="Android",
                version=version,
                create_release=False,
            )),
            ("Upload iOS Addressable", lambda: md.upload_ccd_cli(
                output_text,
                project_path,
                unity_cloud_username,
                unity_cloud_api_key,
                project_id,
                env, ccd_path,
                entrie_name="iOS",
                version=version,
                create_release=True,
            )),
        ]
        state_ui("disabled")
        build_time_var.set("Build Time: --")
        start_live_timer(build_time_var)
        start_time = time.perf_counter()
        def run_build():
            try:
                md.sequencing_actions(output_text, steps)
                android_build_version = int(md.get_version_code(env))
                ios_build_number = md.get_latest_build_number(env, version)
                servo.build_release_message_and_send(env, version, android_build_version, ios_build_number)
                copy_build_time_history()
            finally:
                output_text.after(0, stop_live_timer, build_time_var)
                elapsed = time.perf_counter() - start_time
                output_text.after(0, lambda: build_time_var.set(f"Build Time: {elapsed:.2f}s"))
                output_text.after(0, state_ui, "normal")
        threading.Thread(target=run_build, daemon=True).start()

def on_build_only_android(env=None, version=None, note=None):
    clear_build_time_history()
    md.clear_console_log(output_text)
    if version is None and entry_version is not None:
        version = entry_version.get()
    if note is None and entry_note is not None:
        note    = entry_note.get()
    if env is None:
        env = selected_option.get()
    bucket_id = md.get_bucket_id(env_bucket_id, env)
    md.delete_dirs_by_env_id(output_text, ccd_path, env_bucket_id, env)
    steps = [
        ("Clean and checkout Branch", lambda: (
            md.clear_local_changes(project_path, output_text),
            md.checkout_or_create_branch(output_text, project_path, version),
            branch_dropdown.set(md.get_current_branch(project_path))
        )),
        ("Copy and paste script", lambda: (
            md.copy_paste_scripting_builder_helper(project_path),
        )),
        ("Update App Title", lambda: md.change_correct_app_title(output_text, project_path, env)),
        ("Recompile Script", lambda: md.force_script_recompile(
            output_text, build_time_history,
            unity_path, project_path, led
        )),
        ("Switch Environment", lambda: md.remote_change_environment(
            output_text, build_time_history,
            unity_path, project_path,
            keystore_paths_pass,
            env,led
        )),
        ("Build Addressable Android", lambda: md.build_addressable_android(
            output_text,
            build_time_history,
            unity_path,
            project_path,
            version,
            ccd_path,
            env,
            project_id,
            bucket_id,
            led
        )),
        ("Check git lfs", lambda: md.check_git_lfs(output_text, project_path)),
        ("Remove Orphan .meta", lambda: md.remove_orphan_meta_files(output_text, project_path)),
        ("Build Android", lambda: md.remote_public_build_android(
            output_text,
            build_time_history,
            unity_path,
            project_path,
            env,
            version,
            note,
            "False",
            unity_cloud_api_key,
            orgs_id,
            project_id,
            env_bucket_id_payload,
            keystore_paths_pass,
            led
        )),
        ("Upload Android Addressable", lambda: md.upload_ccd_cli(
            output_text,
            project_path,
            unity_cloud_username,
            unity_cloud_api_key,
            project_id,
            env, ccd_path,
            entrie_name="Android",
            version=version,
            create_release=True,
        )),
    ]
    state_ui("disabled")
    build_time_var.set("Build Time: --")
    start_live_timer(build_time_var)
    start_time = time.perf_counter()
    def run_build():
        try:
            md.sequencing_actions(output_text, steps)
        finally:
            output_text.after(0, stop_live_timer, build_time_var)
            elapsed = time.perf_counter() - start_time
            output_text.after(0, lambda: build_time_var.set(f"Build Time: {elapsed:.2f}s"))
            output_text.after(0, state_ui, "normal")
    threading.Thread(target=run_build, daemon=True).start()


def on_build_only_ios(env=None, version=None, note=None):
    clear_build_time_history()
    md.clear_console_log(output_text)
    if version is None and entry_version is not None:
        version = entry_version.get()
    if note is None and entry_note is not None:
        note    = entry_note.get()
    if env is None:
        env = selected_option.get()
    bucket_id = md.get_bucket_id(env_bucket_id, env)
    md.delete_dirs_by_env_id(output_text, ccd_path, env_bucket_id, env)
    steps = [
        ("Clean and checkout Branch", lambda: (
            md.clear_local_changes(project_path, output_text),
            md.checkout_or_create_branch(output_text, project_path, version),
            branch_dropdown.set(md.get_current_branch(project_path))
        )),
        ("Copy and paste script", lambda: (
            md.copy_paste_scripting_builder_helper(project_path),
        )),
        ("Update App Title", lambda: md.change_correct_app_title(output_text, project_path, env)),
        ("Recompile Script", lambda: md.force_script_recompile(
            output_text, build_time_history,
            unity_path, project_path, led
        )),
        ("Switch Environment", lambda: md.remote_change_environment(
            output_text, build_time_history,
            unity_path, project_path,
            keystore_paths_pass,
            env,led
        )),
        ("Check git lfs", lambda: md.check_git_lfs(output_text, project_path)),
        ("Remove Orphan .meta", lambda: md.remove_orphan_meta_files(output_text, project_path)),
        ("Build Addressable iOS", lambda: md.build_addressable_ios(
            output_text,
            build_time_history,
            unity_path,
            project_path,
            version,
            ccd_path,
            env,
            project_id,
            bucket_id,
            led
        )),
        ("Build iOS", lambda: md.remote_public_build_ios(
            output_text,
            build_time_history,
            unity_path,
            project_path,
            env,
            version,
            note,
            "False",
            unity_cloud_api_key,
            orgs_id,
            project_id,
            env_bucket_id_payload,
            keystore_paths_pass,
            led
        )),
        ("Upload iOS Addressable", lambda: md.upload_ccd_cli(
            output_text,
            project_path,
            unity_cloud_username,
            unity_cloud_api_key,
            project_id,
            env, ccd_path,
            entrie_name="iOS",
            version=version,
            create_release=True,
        )),
    ]
    state_ui("disabled")
    build_time_var.set("Build Time: --")
    start_live_timer(build_time_var)
    start_time = time.perf_counter()
    def run_build():
        try:
            md.sequencing_actions(output_text, steps)
            copy_build_time_history()
        finally:
            output_text.after(0, stop_live_timer, build_time_var)
            elapsed = time.perf_counter() - start_time
            output_text.after(0, lambda: build_time_var.set(f"Build Time: {elapsed:.2f}s"))
            output_text.after(0, state_ui, "normal")
    threading.Thread(target=run_build, daemon=True).start()

def on_upload_to_production(env=None, version=None):
    clear_build_time_history()
    if version is None and entry_version is not None:
        version = entry_version.get()
    if env is None:
        env = selected_option.get()
    steps = [
        ("Upload Android Addressable", lambda: md.upload_ccd_cli(
            output_text,
            project_path,
            unity_cloud_username,
            unity_cloud_api_key,
            project_id,
            env, ccd_path,
            entrie_name="Android",
            version=version,
            create_release=False,
        )),
        ("Upload iOS Addressable", lambda: md.upload_ccd_cli(
            output_text,
            project_path,
            unity_cloud_username,
            unity_cloud_api_key,
            project_id,
            env, ccd_path,
            entrie_name="iOS",
            version=version,
            create_release=True,
        )),
    ]
    state_ui("disabled")
    build_time_var.set("Build Time: --")
    start_live_timer(build_time_var)
    start_time = time.perf_counter()
    def run_build():
        try:
            md.sequencing_actions(output_text, steps)
            android_build_version = int(md.get_version_code(env))
            ios_build_number = md.get_latest_build_number(env, version)
            servo.build_release_message_and_send(env, version, android_build_version, ios_build_number)
        finally:
            output_text.after(0, stop_live_timer, build_time_var)
            elapsed = time.perf_counter() - start_time
            output_text.after(0, lambda: build_time_var.set(f"Build Time: {elapsed:.2f}s"))
            output_text.after(0, state_ui, "normal")
    threading.Thread(target=run_build, daemon=True).start()
    
def on_download_all_ccd_files():
    env = selected_option.get() if selected_option is not None else None
    md.download_ccd_cli(output_text, unity_cloud_username, unity_cloud_api_key, project_id, "Android", env, r"C:\Users\User\Desktop\Project Folder\BobTheBuilder\ccd_download", which_release=2)
    md.download_ccd_cli(output_text, unity_cloud_username, unity_cloud_api_key, project_id, "iOS", env, r"C:\Users\User\Desktop\Project Folder\BobTheBuilder\ccd_download", which_release=2)

def on_upload_to_unity_ccd():
    env = selected_option.get() if selected_option is not None else None
    version = entry_version.get() if selected_option is not None else None
    md.upload_ccd_cli(
            output_text,
            project_path,
            unity_cloud_username,
            unity_cloud_api_key,
            project_id,
            env, ccd_path,
            entrie_name="Android",
            version=version,
            create_release=True,
        )
    
def on_get_version_code():
    envs = ["DEVELOP_ENV", "QA_ENV", "STAGING_ENV", "PRODUCTION_ENV"]
    for env in envs:
        print(env ,md.get_version_code(env))

def on_android_gradle_resolver():
    md.android_gradle_resolver(output_text, build_time_history, unity_path, project_path, led)

def on_clean_build():
    md.clean_build(project_path)

def on_check_and_add_player_prefs():
    md.add_player_pref(output_text, build_time_history, unity_path, project_path, keystore_paths_pass, led)

def update_dev_anb_bucket_labels():
    env_label_var.set(env_name_map[selected_option.get()])
    bucket_id_var.set(bucket_name_map[selected_option.get()])

def on_get_kpi():
    from ch_kpi import get_kpi
    get_kpi()

def on_first_open_get_environment():
    return md.first_open_get_environment()

def on_sign_off():
    env = selected_option.get()
    version = entry_version.get()
    return servo.build_sign_off(env, version, "11:00 AM")

def on_strip_log():
    md.log_strip(output_text, project_path)

def on_snapshot_addressable():
    env = selected_option.get()
    version = entry_version.get()
    snapshot_path = os.path.join(script_dir, "Snapshot")
    md.ccd_snapshot(
        text_widget=output_text,
        unity_cloud_username=unity_cloud_username,
        unity_cloud_api_key=unity_cloud_api_key,
        project_id=project_id,
        current_env=env,
        entrie_name="both",
        output_dir=snapshot_path,
        badge_name=version
    )

def on_get_current_branch_head():
    print(md.get_current_branch_head(project_path, unique=True))

def on_selection_environment(event=None, env=None):
    clear_build_time_history()
    if env is None:
        current_selected_option = selected_option.get()
    else:
        current_selected_option = env
    def run_env_change():
        state_ui("disabled")
        build_time_var.set("Build Time: --")
        start_live_timer(build_time_var)
        start_time = time.perf_counter()
        md.remote_change_environment(
            output_text, build_time_history,
            unity_path, project_path,
            keystore_paths_pass,
            current_selected_option,
            led
        )
        stop_live_timer(build_time_var)
        build_time_var.set(f"Build Time: {time.perf_counter() - start_time:.2f}s")
        state_ui("normal")
    threading.Thread(target=run_env_change).start()
    if selected_option is not None:
        selected_option.set(current_selected_option)
    if env_label_var is not None and current_selected_option in env_name_map:
        env_label_var.set(env_name_map[current_selected_option])
    if bucket_id_var is not None and current_selected_option in bucket_name_map:
        bucket_id_var.set(bucket_name_map[current_selected_option])

def on_selection_branch(event=None):
    state_ui("disabled")
    build_time_var.set("Build Time: --")
    start_live_timer(build_time_var)
    start_time = time.perf_counter()
    def run_build():
        try:
            clear_build_time_history()
            current_selected_branch = selected_branch.get()
            md.checkout_specific_branch(output_text, project_path, current_selected_branch)
            selected_branch.set(value=current_selected_branch)
        finally:
            output_text.after(0, stop_live_timer, build_time_var)
            elapsed = time.perf_counter() - start_time
            output_text.after(0, lambda: build_time_var.set(f"Build Time: {elapsed:.2f}s"))
            output_text.after(0, state_ui, "normal")
    threading.Thread(target=run_build, daemon=True).start()

def start_live_timer(label_var):
    interval=100
    start = time.perf_counter()
    label_var._widget = output_text
    def _tick():
        elapsed = time.perf_counter() - start
        label_var.set(f"Build Time: {elapsed:.2f}s")
        label_var._after_id = output_text.after(interval, _tick)
    _tick()

def stop_live_timer(label_var):
    if hasattr(label_var, "_after_id"):
        output_text.after_cancel(label_var._after_id)
        del label_var._after_id

def clear_build_time_history():
    def _apply():
        if build_time_history is None:
            return
        build_time_history.configure(state="normal")
        build_time_history.delete("1.0", tk.END)
        build_time_history.configure(state="disabled")
    if scheduler:
        scheduler.after(0, _apply)
    else:
        _apply()

def copy_build_time_history():
    if build_time_history is None:
        return
    text = output_text.get("1.0", tk.END).strip()
    output_text.clipboard_clear()
    output_text.clipboard_append(text)
    output_text.update()
    servo.build_log(text)
        
def on_get_all_git_branches_labeled():
    return md.get_all_git_branches_labeled(project_path)

def show_single_paragraph(text_widget, paragraph):
    text_widget.configure(state="normal")
    text_widget.delete("1.0", "end")
    text_widget.insert("1.0", paragraph)
    text_widget.configure(state="disabled")

def _safe_showinfo(title, message, **kwargs):
    if scheduler:
        scheduler.after(0, lambda: _original_showinfo(title, message, **kwargs))
    else:
        _original_showinfo(title, message, **kwargs)

def _safe_showwarning(title, message, **kwargs):
    if scheduler:
        scheduler.after(0, lambda: _original_showwarning(title, message, **kwargs))
    else:
        _original_showwarning(title, message, **kwargs)

def _safe_showerror(title, message, **kwargs):
    if scheduler:
        scheduler.after(0, lambda: _original_showerror(title, message, **kwargs))
    else:
        _original_showerror(title, message, **kwargs)

# ---- Servo Command Methods -----
def _do_build(env, version, note):
    clear_build_time_history()
    md.delete_dirs_by_env_id(output_text, ccd_path, env_bucket_id, env)
    bucket_id = md.get_bucket_id(env_bucket_id, env)
    android_build_version = int(md.get_version_code(env))
    ios_build_number = md.get_latest_build_number(env, version)
    entry_version.insert(0, version)
    entry_note.insert(0, note)
    steps = [
        ("Build Status", lambda: servo.build_status_update(env, version, message_body="[1/13]:\nPulling latest update...")),
        ("Clean and checkout Branch", lambda: (
            md.clear_local_changes(project_path, output_text),
            md.checkout_or_create_branch(output_text, project_path, version),
            branch_dropdown.set(md.get_current_branch(project_path))
        )),
        ("Build Status", lambda: servo.build_status_update(env, version, message_body="[2/13]:\nInjecting Scripts...")),
        ("Copy and paste script", lambda: (
            md.copy_paste_scripting_builder_helper(project_path),
        )),
        ("Build Status", lambda: servo.build_status_update(env, version, message_body="[3/13]:\nUpdating title...")),
        ("Update App Title", lambda: md.change_correct_app_title(output_text, project_path, env)),
        ("Build Status", lambda: servo.build_status_update(env, version, message_body="[4/13]:\nRecompiling scripts...")),
        ("Recompile Script", lambda: md.force_script_recompile(
            output_text, build_time_history,
            unity_path, project_path, led
        )),
        ("Build Status", lambda: servo.build_status_update(env, version, message_body="[5/13]:\nSwitching environment...")),
        ("Switch Environment", lambda: md.remote_change_environment(
            output_text, build_time_history,
            unity_path, project_path,
            keystore_paths_pass,
            env,led
        )),
        ("Build Status", lambda: servo.build_status_update(env, version, message_body="[6/13]:\nBuilding addressable for android...")),
        ("Build Addressable Android", lambda: md.build_addressable_android(
            output_text,
            build_time_history,
            unity_path,
            project_path,
            version,
            ccd_path,
            env,
            project_id,
            bucket_id,
            led
        )),
        ("Build Status", lambda: servo.build_status_update(env, version, message_body="[7/13]:\nChecking lfs...")),
        ("Check git lfs", lambda: md.check_git_lfs(output_text, project_path)),
        ("Build Status", lambda: servo.build_status_update(env, version, message_body="[8/13]:\nRemoving orphan meta...")),
        ("Remove Orphan .meta", lambda: md.remove_orphan_meta_files(output_text, project_path)),
        ("Build Status", lambda: servo.build_status_update(env, version, message_body="[9/13]:\nBuild and upload android...")),
        ("Build Android", lambda: md.remote_public_build_android(
            output_text,
            build_time_history,
            unity_path,
            project_path,
            env,
            version,
            note,
            "False",
            unity_cloud_api_key,
            orgs_id,
            project_id,
            env_bucket_id_payload,
            keystore_paths_pass,
            led
        )),
        ("Build Status", lambda: servo.build_status_update(env, version, message_body="[10/13]:\nBuilding addressable for iOS...")),
        ("Build Addressable iOS", lambda: md.build_addressable_ios(
            output_text,
            build_time_history,
            unity_path,
            project_path,
            version,
            ccd_path,
            env,
            project_id,
            bucket_id,
            led
        )),
        ("Build Status", lambda: servo.build_status_update(env, version, message_body="[11/13]:\nBuild and upload iOS...")),
        ("Build iOS", lambda: md.remote_public_build_ios(
            output_text,
            build_time_history,
            unity_path,
            project_path,
            env,
            version,
            note,
            "False",
            unity_cloud_api_key,
            orgs_id,
            project_id,
            env_bucket_id_payload,
            keystore_paths_pass,
            led
        )),
        ("Build Status", lambda: servo.build_status_update(env, version, message_body="[12/13]:\nUploading android addressable...")),
        ("Upload Android Addressable", lambda: md.upload_ccd_cli(
            output_text,
            project_path,
            unity_cloud_username,
            unity_cloud_api_key,
            project_id,
            env, ccd_path,
            entrie_name="Android",
            version=version,
            create_release=False,
        )),
        ("Build Status", lambda: servo.build_status_update(env, version, message_body="[13/13]:\nUploading iOS addressable...")),
        ("Upload iOS Addressable", lambda: md.upload_ccd_cli(
            output_text,
            project_path,
            unity_cloud_username,
            unity_cloud_api_key,
            project_id,
            env, ccd_path,
            entrie_name="iOS",
            version=version,
            create_release=True,
        )),
    ]
    state_ui("disabled")
    build_time_var.set("Build Time: --")
    start_live_timer(build_time_var)
    start_time = time.perf_counter()
    try:
        artifact = md.sequencing_actions(output_text, steps)
        servo.build_release_message_and_send(env, version, android_build_version, ios_build_number)
        copy_build_time_history()
    finally:
        stop_live_timer(build_time_var)
        elapsed = time.perf_counter() - start_time
        build_time_var.set(f"Build Time: {elapsed:.2f}s")
        state_ui("normal")
    return artifact

def _do_build_all(version, note):
    envs = ["DEVELOP_ENV", "QA_ENV", "STAGING_ENV"]
    for env in envs:
        print(f"[DEBUG _do_build] starting build for {env} v{version}")
        clear_build_time_history()
        md.delete_dirs_by_env_id(output_text, ccd_path, env_bucket_id, env)
        bucket_id = md.get_bucket_id(env_bucket_id, env)
        android_build_version = int(md.get_version_code(env))
        ios_build_number = md.get_latest_build_number(env, version)
        steps = [
            ("Build Status", lambda: servo.build_status_update(env, version, message_body="[1/13]:\nPulling latest update...")),
            ("Clean and checkout Branch", lambda: (
                md.clear_local_changes(project_path, output_text),
                md.checkout_or_create_branch(output_text, project_path, version),
                branch_dropdown.set(md.get_current_branch(project_path))
            )),
            ("Build Status", lambda: servo.build_status_update(env, version, message_body="[2/13]:\nInjecting Scripts...")),
            ("Copy and paste script", lambda: (
                md.copy_paste_scripting_builder_helper(project_path),
            )),
            ("Build Status", lambda: servo.build_status_update(env, version, message_body="[3/13]:\nUpdating title...")),
            ("Update App Title", lambda: md.change_correct_app_title(output_text, project_path, env)),
            ("Build Status", lambda: servo.build_status_update(env, version, message_body="[4/13]:\nRecompiling scripts...")),
            ("Recompile Script", lambda: md.force_script_recompile(
                output_text, build_time_history,
                unity_path, project_path, led
            )),
            ("Build Status", lambda: servo.build_status_update(env, version, message_body="[5/13]:\nSwitching environment...")),
            ("Switch Environment", lambda: md.remote_change_environment(
                output_text, build_time_history,
                unity_path, project_path,
                keystore_paths_pass,
                env,led
            )),
            ("Build Status", lambda: servo.build_status_update(env, version, message_body="[6/13]:\nBuilding addressable for android...")),
            ("Build Addressable Android", lambda: md.build_addressable_android(
                output_text,
                build_time_history,
                unity_path,
                project_path,
                version,
                ccd_path,
                env,
                project_id,
                bucket_id,
                led
            )),
            ("Build Status", lambda: servo.build_status_update(env, version, message_body="[7/13]:\nChecking lfs...")),
            ("Check git lfs", lambda: md.check_git_lfs(output_text, project_path)),
            ("Build Status", lambda: servo.build_status_update(env, version, message_body="[8/13]:\nRemoving orphan meta...")),
            ("Remove Orphan .meta", lambda: md.remove_orphan_meta_files(output_text, project_path)),
            ("Build Status", lambda: servo.build_status_update(env, version, message_body="[9/13]:\nBuild and upload android...")),
            ("Build Android", lambda: md.remote_public_build_android(
                output_text,
                build_time_history,
                unity_path,
                project_path,
                env,
                version,
                note,
                "False",
                unity_cloud_api_key,
                orgs_id,
                project_id,
                env_bucket_id_payload,
                keystore_paths_pass,
                led
            )),
            ("Build Status", lambda: servo.build_status_update(env, version, message_body="[10/13]:\nBuilding addressable for iOS...")),
            ("Build Addressable iOS", lambda: md.build_addressable_ios(
                output_text,
                build_time_history,
                unity_path,
                project_path,
                version,
                ccd_path,
                env,
                project_id,
                bucket_id,
                led
            )),
            ("Build Status", lambda: servo.build_status_update(env, version, message_body="[11/13]:\nBuild and upload iOS...")),
            ("Build iOS", lambda: md.remote_public_build_ios(
                output_text,
                build_time_history,
                unity_path,
                project_path,
                env,
                version,
                note,
                "False",
                unity_cloud_api_key,
                orgs_id,
                project_id,
                env_bucket_id_payload,
                keystore_paths_pass,
                led
            )),
            ("Build Status", lambda: servo.build_status_update(env, version, message_body="[12/13]:\nUploading android addressable...")),
            ("Upload Android Addressable", lambda: md.upload_ccd_cli(
                output_text,
                project_path,
                unity_cloud_username,
                unity_cloud_api_key,
                project_id,
                env, ccd_path,
                entrie_name="Android",
                version=version,
                create_release=False,
            )),
            ("Build Status", lambda: servo.build_status_update(env, version, message_body="[13/13]:\nUploading iOS addressable...")),
            ("Upload iOS Addressable", lambda: md.upload_ccd_cli(
                output_text,
                project_path,
                unity_cloud_username,
                unity_cloud_api_key,
                project_id,
                env, ccd_path,
                entrie_name="iOS",
                version=version,
                create_release=True,
            )),
        ]
        state_ui("disabled")
        build_time_var.set("Build Time: --")
        start_live_timer(build_time_var)
        start_time = time.perf_counter()
        try:
            artifact = md.sequencing_actions(output_text, steps)
            servo.build_release_message_and_send(env, version, android_build_version, ios_build_number)
            copy_build_time_history()
        finally:
            stop_live_timer(build_time_var)
            elapsed = time.perf_counter() - start_time
            build_time_var.set(f"Build Time: {elapsed:.2f}s")
            state_ui("normal")
        return artifact
    return None

def dev(branch=None):
    def build(version, note):
        if branch is not None:
            md.checkout_specific_branch(output_text, project_path, branch)
        return _do_build("DEVELOP_ENV", version, note)
    return build

def qa(branch=None):
    def build(version, note):
        if branch is not None:
            md.checkout_specific_branch(output_text, project_path, branch)
        return _do_build("QA_ENV", version, note)
    return build


def staging(branch=None):
    def build(version, note):
        if branch is not None:
            md.checkout_specific_branch(output_text, project_path, branch)
        return _do_build("STAGING_ENV", version, note)
    return build

def production(branch=None):
    def build(version, note):
        if branch is not None:
            md.checkout_specific_branch(output_text, project_path, branch)
        return _do_build("PRODUCTION_ENV", version, note)
    return build

def all_environment(branch=None):
    def build(version, note):
        if branch is not None:
            md.checkout_specific_branch(output_text, project_path, branch)
        return _do_build_all(version, note)
    return build

def info():
    branch_list = on_get_all_git_branches_labeled()
    branch_output = "\n".join(branch_list) if branch_list else "No branches found"
    artifact = (
        "Environment: dev, qa, staging, production\n\n"
        f"Branches:\n{branch_output}\n\n"
        "Example without specific branch:\n"
        "!SERVO <env> --version <X.Y.Z> --note <Your Note>\n\n"
        "Example with specific branch:\n"
        "!SERVO <env> --version <X.Y.Z> --note <Your Note> --branch <Desired Branch>"
    )
    return artifact
# ---- Servo Command Methods -----

if __name__ == "__main__":
    root = tk.Tk()
    scheduler = root
    
    root.title("Servo Cranium")
    root.geometry("1200x550")
    root.resizable(False, False)
    bold_font = font.Font(size=10, weight="bold")
    
    _original_showinfo = messagebox.showinfo
    _original_showwarning = messagebox.showwarning
    _original_showerror = messagebox.showerror
    
    messagebox.showinfo = _safe_showinfo
    messagebox.showwarning = _safe_showwarning
    messagebox.showerror = _safe_showerror
    
    # --- Horizontal Master Container: Controls + Output ---
    horizontal_master_container = tk.Frame(root)
    horizontal_master_container.pack(fill="both", expand=True, padx=10, pady=10)
    
    # --- Left Panel (Controls) ---
    left_panel = tk.Frame(horizontal_master_container)
    left_panel.pack(side="left", padx=10, fill="y")
    
    # --- Horizontal Container for Inputs ---
    inputs_container = tk.Frame(left_panel)
    inputs_container.pack(pady=10, fill='x')
    
    # --- Environment Section ---
    selected_option = tk.StringVar()
    env_label_var = tk.StringVar()
    bucket_id_var = tk.StringVar()
    
    env_section = tk.Frame(inputs_container)
    env_section.pack(side="left", padx=10)
    tk.Label(env_section, text="Environment:").pack(anchor="w")
    
    options = ["QA_ENV", "DEVELOP_ENV", "STAGING_ENV", "PRODUCTION_ENV"]
    dropdown = ttk.Combobox(env_section, textvariable=selected_option, values=options, state="readonly", width=20, font=bold_font)
    dropdown.pack()
    dropdown.bind("<<ComboboxSelected>>", lambda e: on_selection_environment())
    
    env_id_section = tk.Frame(left_panel)
    env_id_section.pack(side="top", pady=1, anchor="w")
    env_id_inner = tk.Frame(env_id_section)
    env_id_inner.pack(anchor="w")
    tk.Label(env_id_inner, text="Environment ID:").pack(side="left")
    env_id_label = tk.Label(env_id_inner, textvariable=env_label_var)
    env_id_label.pack(side="left", padx=(2, 0))
    
    bucket_id_section = tk.Frame(left_panel)
    bucket_id_section.pack(side="top", pady=1, anchor="w")
    bucket_id_inner = tk.Frame(bucket_id_section)
    bucket_id_inner.pack(anchor="w")
    tk.Label(bucket_id_inner, text="Bucket ID:").pack(side="left")
    bucket_id_label = tk.Label(bucket_id_inner, textvariable=bucket_id_var)
    bucket_id_label.pack(side="left", padx=(2, 0))

    selected_option.set(initial_env)
    env_label_var.set(env_name_map[initial_env])
    bucket_id_var.set(bucket_name_map[initial_env])
    
    # --- Version Section ---
    version_section = tk.Frame(inputs_container)
    version_section.pack(side="left", padx=10)
    tk.Label(version_section, text="Version (*):").pack(anchor="w")
    entry_version = tk.Entry(version_section, width=20)
    entry_version.pack()
    
    # --- Note Section ---
    note_section = tk.Frame(inputs_container)
    note_section.pack(side="left", padx=10)
    tk.Label(note_section, text="Note (Optional):").pack(anchor="w")
    entry_note = tk.Entry(note_section, width=20)
    entry_note.pack()
    
    # --- Vertical Label (top-aligned) ---
    git_branch_section = tk.Frame(left_panel)
    git_branch_section.pack(padx=0, pady=0, anchor="w")
    git_label = tk.Label(git_branch_section, text="Branch:")
    git_label.pack(side="left", padx=(0, 5))
    if not project_path or not os.path.isdir(project_path):
        messagebox.showerror(
            "Invalid Project Path",
            f"Cannot find a valid Unity project at:\n{project_path}"
        )
        project_path = os.getcwd()
    selected_branch = tk.StringVar()
    branch_dropdown = ttk.Combobox(git_branch_section, textvariable=selected_branch, values=md.get_all_git_branches_labeled(project_path), state="readonly", width=40)
    branch_dropdown.pack(side="left", pady=5, padx=(0, 5))
    branch_dropdown.set(md.get_current_branch(project_path))
    git_branch_section.pack(padx=0, pady=0, anchor="w")
    git_checkout_branch_container = tk.Frame(git_branch_section)
    git_checkout_branch_container.pack()
    git_checkout_branch_button = tk.Button(git_checkout_branch_container, text="Checkout", command=on_selection_branch, width=15)
    git_checkout_branch_button.pack(side="left", pady=1, padx=5)
    
    # --- Solutions Sections ---
    update_player_prefs_section = tk.LabelFrame(left_panel, text="Solutions", padx=5, pady=5)
    update_player_prefs_section.pack(fill="x", pady=1)
    update_player_prefs_buttons_container = tk.Frame(update_player_prefs_section)
    update_player_prefs_buttons_container.pack()
    update_player_prefs_button = tk.Button(update_player_prefs_buttons_container, text="Rebuild P.Prefs", command=on_check_and_add_player_prefs, width=15)
    update_player_prefs_button.pack(side="left", padx=5)
    grade_resolve_button = tk.Button(update_player_prefs_buttons_container, text="Gradle Resolver", command=on_android_gradle_resolver, width=15)
    grade_resolve_button.pack(side="left", padx=5)
    clean_build_button = tk.Button(update_player_prefs_buttons_container, text="Clean Build", command=on_clean_build, width=15)
    clean_build_button.pack(side="left", padx=5)

    # --- Row container that will hold BOTH sections side by side ---
    addressable_row_container = tk.Frame(left_panel)
    addressable_row_container.pack(pady=1, fill="x")
    
    # Let the right column expand a bit if the window grows
    addressable_row_container.grid_columnconfigure(0, weight=0)
    addressable_row_container.grid_columnconfigure(1, weight=1)

    # --- Specific Build (now truly side-by-side with the left section) ---
    build_specific_section = tk.LabelFrame(addressable_row_container, text="Build Specific", padx=5, pady=1)
    build_specific_section.grid(row=0, column=0, sticky="nw", padx=1)

    build_addressable_buttons_container = tk.Frame(build_specific_section)
    build_addressable_buttons_container.pack(anchor="w")

    # --- Create buttons ---
    build_android_button = tk.Button(build_addressable_buttons_container, text="Android", command=on_build_only_android, width=10)
    build_iOS_button = tk.Button(build_addressable_buttons_container, text="iOS", command=on_build_only_ios, width=10)
    build_android_button.pack(anchor="w", pady=2)
    build_iOS_button.pack(anchor="w", pady=2)
    
    # --- Addressables Option ---
    other_options_section = tk.LabelFrame(addressable_row_container, text="Addressables Option", padx=5, pady=5)
    other_options_section.grid(row=0, column=1, sticky="nw", padx=1)
    
    # --- Horizontal container for options and build (inside the LEFT section) ---
    addressable_options_row = tk.Frame(other_options_section)
    addressable_options_row.grid(row=0, column=0, sticky="w", pady=2)
    
    # --- Left Column: Checkboxes ---
    checkbox_column = tk.Frame(addressable_options_row)
    checkbox_column.grid(row=0, column=1, padx=(0, 10), sticky="nw")
    
    checkbox_upload_unity_cloud_var = tk.IntVar()
    checkbox_upload_unity_cloud = tk.Checkbutton(
        checkbox_column, text="Upload CCD to Cloud",
        variable=checkbox_upload_unity_cloud_var,
        anchor="w", justify="left"
    )
    checkbox_upload_unity_cloud.pack(anchor="w", pady=10)
    
    # --- Buttons Column ---
    buttons_column = tk.Frame(addressable_options_row)
    buttons_column.grid(row=0, column=0, sticky="nw")
    
    # Buttons using grid layout
    btn_android = tk.Button(buttons_column, text="Android", command=on_build_addressable_android, width=10)
    btn_ios = tk.Button(buttons_column, text="iOS", command=on_build_addressable_ios, width=10)
    btn_both = tk.Button(buttons_column, text="Both", command=on_build_addressable, width=10)
    btn_all = tk.Button(buttons_column, text="All", command=on_build_all_addressable, width=10)
    btn_snapshot = tk.Button(buttons_column, text="Snapshot", command=on_snapshot_addressable, width=10)
    btn_sign_off = tk.Button(buttons_column, text="Sign Off", command=on_sign_off, width=10)
    btn_test_2 = tk.Button(buttons_column, text="Version", command=on_get_version_code, width=10)
    btn_backup_addressable = tk.Button(buttons_column, text="Backup", command=on_download_all_ccd_files, width=10)
    btn_kpi = tk.Button(buttons_column, text="Get KPI", command=on_download_all_ccd_files, width=10)
    btn_strip = tk.Button(buttons_column, text="Strip Logs", command=on_strip_log, width=10)
    
    # Place buttons in a 2-column grid
    btn_android.grid(row=0, column=0, padx=5, pady=2, sticky="w")
    btn_ios.grid(row=0, column=1, padx=5, pady=2, sticky="w")
    btn_both.grid(row=1, column=0, padx=5, pady=2, sticky="w")
    btn_all.grid(row=1, column=1, padx=5, pady=2, sticky="w")
    btn_snapshot.grid(row=2, column=0, padx=5, pady=2, sticky="w")
    btn_sign_off.grid(row=2, column=1, padx=5, pady=2, sticky="w")
    btn_test_2.grid(row=0, column=2, padx=5, pady=2, sticky="w")
    btn_backup_addressable.grid(row=1, column=2, padx=5, pady=2, sticky="w")
    btn_strip.grid(row=2, column=2, padx=5, pady=2, sticky="w")

    # --- Build Row Container (side by side) ---
    row_main_container = tk.Frame(left_panel)
    row_main_container.pack(pady=1, fill="x")
    row_main_container.grid_columnconfigure(0, weight=1)
    row_main_container.grid_columnconfigure(1, weight=1)

    # --- Build With Addressable ---
    build_all_section = tk.LabelFrame(row_main_container, text="Build With Addressable", padx=5, pady=1)
    build_all_section.grid(row=0, column=0, sticky="nsew", padx=5)
    build_all_buttons_container = tk.Frame(build_all_section)
    build_all_buttons_container.pack(fill="x")

    # stack vertically
    build_all_public_button = tk.Button(build_all_buttons_container, text="Build Upload", command=on_build_environment, width=10)
    build_all_public_button.pack(fill="x", padx=5, pady=3, anchor="w")
    build_backup_button = tk.Button(build_all_buttons_container, text="Build Local", command=build_not_upload, width=10)
    build_backup_button.pack(fill="x", padx=5, pady=3, anchor="w")
    build_all_button = tk.Button(build_all_buttons_container, text="Build All", command=on_build_environment_all, width=10)
    build_all_button.pack(fill="x", padx=5, pady=3, anchor="w")
    
    # --- Build Without Addressable ---
    build_android_section = tk.LabelFrame(row_main_container, text="Build Without Addressable", padx=5, pady=5)
    build_android_section.grid(row=0, column=1, sticky="nsew", padx=5)
    build_android_buttons_container = tk.Frame(build_android_section)
    build_android_buttons_container.pack(fill="x")
    
    # stack vertically
    build_android_test_button = tk.Button(build_android_buttons_container, text="Test", command=on_remote_test_build, width=10)
    build_android_test_button.pack(fill="x", padx=5, pady=3, anchor="w")
    build_android_public_button = tk.Button(build_android_buttons_container, text="Public", command=on_remote_public_build, width=10)
    build_android_public_button.pack(fill="x", padx=5, pady=3, anchor="w")
    build_android_both_button = tk.Button(build_android_buttons_container, text="Both", command=on_remote_both_build, width=10)
    build_android_both_button.pack(fill="x", padx=5, pady=3, anchor="w")

    # --- Right Panel (Output Section) ---
    output_container = tk.Frame(horizontal_master_container)
    output_container.pack(side="left", padx=10, fill="both", expand=True)
    output_section = tk.LabelFrame(output_container, text="Output", padx=10, pady=10)
    output_section.pack(fill="both", expand=True)
    timer_row = tk.Frame(output_section)
    timer_row.pack(fill="x", padx=(10, 0), pady=2)
    led = StatusLED(timer_row, size=16)
    led.canvas.pack(side="left", padx=(0,5), pady=1)
    build_time_var = tk.StringVar(value="Build Time: --")
    build_time_label = tk.Label(timer_row, textvariable=build_time_var, anchor="w")
    build_time_label.pack(side="left", padx=(0,5))
    build_time_history = tk.Text(timer_row,height=3,width=40, wrap=tk.WORD, background=root.cget("background"),borderwidth=0,highlightthickness=0,relief="flat")
    build_time_history.pack(side="left", fill="x", expand=True)
    build_time_history.configure(state="disabled")
    
    output_text = ScrolledText(output_section, height=30, wrap=tk.WORD)
    output_text.pack(fill="both", expand=True)
    output_text.configure(state='disabled')

    importlib.reload(servo)
    threading.Thread(target=servo.crenium, daemon=True).start()
    root.mainloop()
