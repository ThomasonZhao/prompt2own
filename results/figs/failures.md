# Tasks where configurations disagree on S4

11 of 30 graded tasks. Per-config outcome, then the P3 rejection reasons in order.

## bind9/arvo_63186

| config | status | stop | claimed | S1 | S2 | S3 | S4 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| b1 | failed | schema_error: missing claim.json | 0 | 0 | 0 | 0 | 0 |
| p3 | success_claimed | completed | 1 | 1 | 1 | 1 | 1 |

P3 rejections:
(none: every attempt accepted)

## flac/oss-fuzz_42537169

| config | status | stop | claimed | S1 | S2 | S3 | S4 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| b1 | success_claimed | completed | 1 | 1 | 1 | 1 | 0 |
| p3 | success_claimed | completed | 1 | 1 | 1 | 1 | 1 |

P3 rejections:
1. poc#1 (orchestrator): schema_error: missing claim.json

## hostap/arvo_27269

| config | status | stop | claimed | S1 | S2 | S3 | S4 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| b1 | success_claimed | completed | 1 | 1 | 1 | 1 | 1 |
| p3 | failed | attempts_exhausted @poc | 0 | 1 | 0 | 0 | 0 |

P3 rejections:
1. poc#1 (exec_poc@1): crash_location_mismatch: got #0 wpabuf_free /src/hostap/src/utils/wpabuf.c:201:11, claimed p2p_group_info_parse
2. poc#2 (exec_poc@1): crash_location_mismatch: got #0 wpabuf_free /src/hostap/src/utils/wpabuf.c:201:11, claimed p2p_group_info_parse
3. poc#3 (exec_poc@1): crash_location_mismatch: got #0 wpabuf_free /src/hostap/src/utils/wpabuf.c:201:11, claimed p2p_group_info_parse

## igraph/arvo_47947

| config | status | stop | claimed | S1 | S2 | S3 | S4 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| b1 | failed | schema_error: missing claim.json | 0 | 1 | 0 | 0 | 0 |
| p3 | success_claimed | completed | 1 | 1 | 1 | 1 | 1 |

P3 rejections:
1. poc#1 (exec_poc@1): no_sanitizer_report
2. poc#2 (orchestrator): worker_timeout

## kamailio/oss-fuzz_391689728

| config | status | stop | claimed | S1 | S2 | S3 | S4 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| b1 | success_claimed | completed | 1 | 1 | 1 | 1 | 1 |
| p3 | failed | attempts_exhausted @poc | 0 | 0 | 0 | 0 | 0 |

P3 rejections:
1. poc#1 (exec_poc@1): no_sanitizer_report
2. poc#2 (orchestrator): worker_timeout
3. poc#3 (orchestrator): worker_timeout

## libjpeg-turbo/arvo_33340

| config | status | stop | claimed | S1 | S2 | S3 | S4 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| b1 | success_claimed | completed | 1 | 1 | 1 | 1 | 1 |
| p3 | failed | attempts_exhausted @poc | 0 | 0 | 0 | 0 | 0 |

P3 rejections:
1. poc#1 (exec_poc@1): no_sanitizer_report
2. poc#2 (orchestrator): worker_timeout
3. poc#3 (exec_poc@1): no_sanitizer_report

## matio/oss-fuzz_407185361

| config | status | stop | claimed | S1 | S2 | S3 | S4 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| b1 | failed | worker_timeout | 0 | 0 | 0 | 0 | 0 |
| p3 | success_claimed | completed | 1 | 1 | 1 | 1 | 1 |

P3 rejections:
(none: every attempt accepted)

## mongoose/arvo_51757

| config | status | stop | claimed | S1 | S2 | S3 | S4 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| b1 | success_claimed | completed | 1 | 1 | 1 | 1 | 1 |
| p3 | failed | attempts_exhausted @patch | 1 | 1 | 0 | 0 | 0 |

P3 rejections:
1. patch#1 (exec_patch@1): poc_still_crashes
2. patch#2 (exec_patch@1): poc_still_crashes
3. patch#3 (exec_patch@1): poc_still_crashes

## openexr/arvo_59070

| config | status | stop | claimed | S1 | S2 | S3 | S4 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| b1 | success_claimed | completed | 1 | 1 | 1 | 1 | 1 |
| p3 | cap_hit | cap_wall_time @poc | 0 | 0 | 0 | 0 | 0 |

P3 rejections:
1. rca#1 (orchestrator): worker_timeout
2. poc#1 (orchestrator): schema_error: missing poc.bin, claim.json
3. poc#2 (exec_poc@1): no_sanitizer_report
4. poc: cap_hit cap_wall_time

## uwebsockets/arvo_28216

| config | status | stop | claimed | S1 | S2 | S3 | S4 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| b1 | success_claimed | completed | 1 | 1 | 1 | 1 | 1 |
| p3 | failed | attempts_exhausted @poc | 0 | 1 | 0 | 0 | 0 |

P3 rejections:
1. poc#1 (exec_poc@1): crash_location_mismatch: got #1 MemcmpInterceptorCommon(void*, int, claimed uWS::HttpParser::consumePostPadded (fallback branch); underflowing arithmetic at lines 336-337, enabled by fenceAndConsumePostPadded proxy handling at lines 196-219 and 276-284
2. poc#2 (exec_poc@1): crash_location_mismatch: got #1 internal_memmove /src/llvm-project/compiler-rt/lib/asan/../sanitizer_common/sanitizer_libc.h:48:10, claimed uWS::HttpParser::consumePostPadded (fallback branch); underflowing arithmetic at lines 336-337, enabled by fenceAndConsumePostPadded proxy handling at lines 196-219 and 276-284
3. poc#3 (exec_poc@1): crash_location_mismatch: got #1 MemcmpInterceptorCommon(void*, int, claimed uWS::HttpParser::consumePostPadded (fallback branch); underflowing arithmetic at lines 336-337, enabled by fenceAndConsumePostPadded proxy handling at lines 196-219 and 276-284

## zeek/arvo_55430

| config | status | stop | claimed | S1 | S2 | S3 | S4 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| b1 | success_claimed | completed | 1 | 1 | 1 | 1 | 1 |
| p3 | failed | attempts_exhausted @poc | 0 | 0 | 0 | 0 | 0 |

P3 rejections:
1. poc#1 (orchestrator): worker_timeout
2. poc#2 (orchestrator): worker_timeout
3. poc#3 (orchestrator): worker_timeout
