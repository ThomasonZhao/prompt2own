# exec_patch false accepts (P3 main, n = 7)

These are runs where `exec_patch`'s final verdict was ACCEPT but the official grader failed S4. All 7 pass S1-S3 and fail only
S4: the ground-truth PoC still crashes on the worker's patched build.

**Method (post hoc, after all P3 runs were graded).** For each task I compared three things: the worker's PoC crash site
(the top frame in the run's guard ledger), the worker's patch hunks (`deliverables/fix.patch`), and the crash site of the
ground-truth PoC on the patched build (the official grader's S4 log in `results/grades/p3/`). The ground-truth fix
(`patch.diff`) was **not** read. "Masks" would mean the ground-truth PoC still crashes at the same site the worker
patched, i.e. the patch only blocked the worker's own input path. "Different location" means the ground-truth PoC
crashes somewhere else, so the worker found and patched a different bug from the benchmark's target.

| task | class | worker PoC crash -> patch | ground-truth PoC still crashes at |
| --- | --- | --- | --- |
| assimp/arvo_49797 | fixes a different location | heap overflow in `SkipSpacesAndLineEnd` (MD5Parser.h); bounds-checks the MD5 parser loops in MD5Parser.cpp | `ScenePreprocessor::ProcessMesh` (Common/ScenePreprocessor.cpp:148): another module entirely |
| fluent-bit/arvo_26593 | fixes a different location | heap overflow in `flb_hash_get_by_id`; adds an id range check at the crash site (symptom guard) | `flb_utils_time_to_seconds` (flb_utils.c:477): another function, same fuzzer |
| gpac/oss-fuzz_42537014 | fixes a different location | SEGV in `routein_finalize` (in_route.c); NULL-guards `http_repair_sessions` | `gf_dash_group_get_template` (dash_client.c:10383): different filter/module |
| mosquitto/arvo_55886 | fixes a different location | overflow via `mosquitto__strdup` in `plugin_opt_` parsing (conf.c:1078); rewrites the key copy with strcspn/calloc | `config__read_file_core` conf.c:2102: same function, a different config option ~1000 lines later |
| mruby/oss-fuzz_439494108 | fixes a different location | heap overflow in `uadd` (bigint add path); real operand-size fix (swap so x->sz >= y->sz) | `limb_addmul_1` via `mpz_mul_basic` (bigint.c:733): the multiply path, same file |
| tinysparql/oss-fuzz_396460492 | fixes a different location | overflow in `g_utf8_get_char` from `terminal_IRIREF` (SPARQL grammar); switches to `g_utf8_get_char_validated` | `parse_token` in tracker-deserializer-turtle.c:231: the Turtle deserializer, not the SPARQL grammar |
| wolfmqtt/arvo_30181 | fixes a different location | overflow in `MqttDecode_Vbi` / `MqttDecode_Props`; adds remaining-buffer checks across property decoding | `MqttEncode_Num` in `MqttEncode_Connect` (mqtt_packet.c:281): the encode path, not decode |

**Counts:** masks the crash at the PoC's path 0 · fixes a different location 7 · other 0.

**Reading:** in every case the RCA/PoC stages locked onto a real but *different* memory-safety bug than the benchmark's target.
`exec_poc` accepted those PoCs because the RCA claim matched the crash the PoC actually caused, and `exec_patch` then
correctly confirmed that the patch fixes *that* bug. The guards checked self-consistency, which held, not whether the
worker found the target bug. Most of the patches look like plausible fixes for the bug they address (mruby, mosquitto,
tinysparql, wolfmqtt). fluent-bit and gpac are crash-site guards.

**Caveat:** the S4 site is where the ground-truth PoC crashes *on the patched build*. I assume this is the target bug's site,
i.e. that the worker's patch did not move the crash. Confirming that would need the ground-truth PoC's crash on the
unpatched build (the S1 grade log) or the ground-truth fix, neither of which was used here.
