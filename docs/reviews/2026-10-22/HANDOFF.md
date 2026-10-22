# comic-translate engineering handoff

Review date: **22 October 2026**. All findings remain **OPEN**. This handoff contains proposed repairs and release checks; no source fixes or new runtime acceptance are claimed.

**Reviewed source:** [`main` at `010048b358cd11e625fedb4d5843b37fa6368e12`](https://github.com/wwongw21/comic-translate/tree/010048b358cd11e625fedb4d5843b37fa6368e12).

The full structured handoff is in [report.json](report.json). Historical commands retain their original review-workspace paths; read the prerequisites before running them. Only repository-specific diagnostics listed below are attached.

## Audience and required outcome

### Audience

1. Maintainer implementing the repairs

2. Reviewer validating save/export contracts

3. Release engineer producing the macOS application

### Outcome

Protect unsaved comic edits and recovery checkpoints, retain queue serialization after failures, preserve every exported page, and restore a buildable macOS packaging path.

## Scope and reviewed branches

Read-only review of default-branch HEAD: worker/task lifecycle, autosave/project container, file and archive import/export, translation/OCR orchestration, dependency declarations and CI.

## Executive assessment

### Priority

Fix COMIC-1 first because an ordinary failed autosave can erase the recovery checkpoint and remove the unsaved-changes warning. Address COMIC-2 next because its failure path breaks the task queue used by saves and processing. COMIC-3 and COMIC-4 are independent repairs.

### Confirmed defects

4

### Highest severity

High

### Evidence strength

Source tracing plus executable control-flow/file-output reproductions. Autosave was independently challenged with real dirty-state methods and a temporary recovery file. No real Qt event-loop session or macOS build was performed.

### Not a claim

The review does not establish that a previous SQLite project is always corrupted or that all autosave failures lose data. It demonstrates false saved-state and recovery deletion on the scoped failure path.

## Architecture

### Item 1

#### Component

Desktop startup and shared application state

#### Files

1. comic.py

2. controller.py

#### Responsibility

comic.py launches the PySide6 application and single-instance/open-project routing. ComicTranslate in controller.py owns page lists, image/history/patch dictionaries, dirty revision, undo group, threadpool and controller instances.

#### Relevant contract

Unsaved-change prompts depend on has_unsaved_changes; set_project_clean clears manual and undo dirty indicators. Worker completions that mark clean therefore affect close behavior.

#### Sources

##### Item 1

###### Path

controller.py

###### Lines

1. 92

2. 139

###### Label

controller.py

###### Url

<https://github.com/wwongw21/comic-translate/blob/010048b358cd11e625fedb4d5843b37fa6368e12/controller.py#L92-L139>

##### Item 2

###### Path

controller.py

###### Lines

1. 373

2. 395

###### Label

controller.py

###### Url

<https://github.com/wwongw21/comic-translate/blob/010048b358cd11e625fedb4d5843b37fa6368e12/controller.py#L373-L395>

##### Item 3

###### Path

controller.py

###### Lines

1. 848

2. 878

###### Label

controller.py

###### Url

<https://github.com/wwongw21/comic-translate/blob/010048b358cd11e625fedb4d5843b37fa6368e12/controller.py#L848-L878>

### Item 2

#### Component

Worker execution and serial task queue

#### Files

1. app/thread_worker.py

2. app/controllers/task_runner.py

#### Responsibility

GenericWorker executes callables/generators in QThreadPool and emits result or error plus an unconditional finished signal. TaskRunnerController queues normal operations and dispatches UI callbacks with QTimer. Immediate operations deliberately bypass the queue.

#### Relevant contract

finished means terminal cleanup, not successful completion. Normal queued work should advance exactly once per operation. Immediate work and per-page batch autosaves are separate concurrency paths.

#### Sources

##### Item 1

###### Path

app/thread_worker.py

###### Lines

1. 19

2. 40

###### Label

app/thread_worker.py

###### Url

<https://github.com/wwongw21/comic-translate/blob/010048b358cd11e625fedb4d5843b37fa6368e12/app/thread_worker.py#L19-L40>

##### Item 2

###### Path

app/controllers/task_runner.py

###### Lines

1. 61

2. 120

###### Label

app/controllers/task_runner.py

###### Url

<https://github.com/wwongw21/comic-translate/blob/010048b358cd11e625fedb4d5843b37fa6368e12/app/controllers/task_runner.py#L61-L120>

##### Item 3

###### Path

app/controllers/task_runner.py

###### Lines

1. 123

2. 170

###### Label

app/controllers/task_runner.py

###### Url

<https://github.com/wwongw21/comic-translate/blob/010048b358cd11e625fedb4d5843b37fa6368e12/app/controllers/task_runner.py#L123-L170>

### Item 3

#### Component

Project save, autosave and recovery orchestration

#### Files

1. app/controllers/projects.py

2. app/projects/project_state.py

3. app/projects/project_state_v2.py

#### Responsibility

ProjectController captures state, launches manual saves, regular/recovery autosaves and direct per-page batch save workers. The project-state writer uses a SQLite container with manifest/page rows and content-addressed image/patch blobs; lazy materialization avoids loading every page immediately.

#### Relevant contract

Only confirmed successful saves may remove recovery or clean an unchanged dirty revision. Manual run_save_proj already has a local failure flag that provides a repository pattern for guarding its finish callback.

#### Sources

##### Item 1

###### Path

app/controllers/projects.py

###### Lines

1. 302

2. 357

###### Label

app/controllers/projects.py

###### Url

<https://github.com/wwongw21/comic-translate/blob/010048b358cd11e625fedb4d5843b37fa6368e12/app/controllers/projects.py#L302-L357>

##### Item 2

###### Path

app/controllers/projects.py

###### Lines

1. 375

2. 431

###### Label

app/controllers/projects.py

###### Url

<https://github.com/wwongw21/comic-translate/blob/010048b358cd11e625fedb4d5843b37fa6368e12/app/controllers/projects.py#L375-L431>

##### Item 3

###### Path

app/controllers/projects.py

###### Lines

1. 1080

2. 1122

###### Label

app/controllers/projects.py

###### Url

<https://github.com/wwongw21/comic-translate/blob/010048b358cd11e625fedb4d5843b37fa6368e12/app/controllers/projects.py#L1080-L1122>

##### Item 4

###### Path

app/projects/project_state_v2.py

###### Lines

1. 226

2. 248

###### Label

app/projects/project_state_v2.py

###### Url

<https://github.com/wwongw21/comic-translate/blob/010048b358cd11e625fedb4d5843b37fa6368e12/app/projects/project_state_v2.py#L226-L248>

### Item 4

#### Component

Image/archive import and translation pipeline

#### Files

1. modules/utils/file_handler.py

2. modules/utils/archives.py

3. pipeline/main_pipeline.py

4. pipeline/batch_processor.py

5. pipeline/ocr_handler.py

6. pipeline/translation_handler.py

#### Responsibility

FileHandler indexes archive/PDF entries and materializes pages lazily. The pipeline coordinates block detection, OCR, translation, inpainting, caches and regular/webtoon batch processing. UI controllers apply results into shared application page state.

#### Relevant contract

These operations share mutable state and use the worker queue, making COMIC-2 relevant beyond project saves. Model inference and live translation behavior were not exercised.

#### Sources

##### Item 1

###### Path

modules/utils/file_handler.py

###### Lines

1. 56

2. 123

###### Label

modules/utils/file_handler.py

###### Url

<https://github.com/wwongw21/comic-translate/blob/010048b358cd11e625fedb4d5843b37fa6368e12/modules/utils/file_handler.py#L56-L123>

##### Item 2

###### Path

pipeline/main_pipeline.py

###### Lines

1. 17

2. 47

###### Label

pipeline/main_pipeline.py

###### Url

<https://github.com/wwongw21/comic-translate/blob/010048b358cd11e625fedb4d5843b37fa6368e12/pipeline/main_pipeline.py#L17-L47>

##### Item 3

###### Path

pipeline/batch_processor.py

###### Lines

1. 92

2. 123

###### Label

pipeline/batch_processor.py

###### Url

<https://github.com/wwongw21/comic-translate/blob/010048b358cd11e625fedb4d5843b37fa6368e12/pipeline/batch_processor.py#L92-L123>

### Item 5

#### Component

Page rendering and archive/PDF export

#### Files

1. app/controllers/projects.py

2. app/ui/canvas/save_renderer.py

3. modules/utils/archives.py

#### Responsibility

ProjectController groups pages, captures viewer state, renders each page into a temporary group directory and calls make() to produce ZIP/CBZ, CB7 or PDF output. Filename generation occurs before packaging; packagers see only files that survive in that directory.

#### Relevant contract

Unique source pages must not map to the same temporary output path. PDF ordering uses a natural sort of generated basenames.

#### Sources

##### Item 1

###### Path

app/controllers/projects.py

###### Lines

1. 556

2. 574

###### Label

app/controllers/projects.py

###### Url

<https://github.com/wwongw21/comic-translate/blob/010048b358cd11e625fedb4d5843b37fa6368e12/app/controllers/projects.py#L556-L574>

##### Item 2

###### Path

app/controllers/projects.py

###### Lines

1. 827

2. 836

###### Label

app/controllers/projects.py

###### Url

<https://github.com/wwongw21/comic-translate/blob/010048b358cd11e625fedb4d5843b37fa6368e12/app/controllers/projects.py#L827-L836>

##### Item 3

###### Path

app/controllers/projects.py

###### Lines

1. 884

2. 930

###### Label

app/controllers/projects.py

###### Url

<https://github.com/wwongw21/comic-translate/blob/010048b358cd11e625fedb4d5843b37fa6368e12/app/controllers/projects.py#L884-L930>

##### Item 4

###### Path

modules/utils/archives.py

###### Lines

1. 452

2. 470

###### Label

modules/utils/archives.py

###### Url

<https://github.com/wwongw21/comic-translate/blob/010048b358cd11e625fedb4d5843b37fa6368e12/modules/utils/archives.py#L452-L470>

##### Item 5

###### Path

modules/utils/archives.py

###### Lines

1. 496

2. 512

###### Label

modules/utils/archives.py

###### Url

<https://github.com/wwongw21/comic-translate/blob/010048b358cd11e625fedb4d5843b37fa6368e12/modules/utils/archives.py#L496-L512>

### Item 6

#### Component

Dependencies and packaging

#### Files

1. requirements.txt

2. .github/workflows/build-macos-dmg.yml

3. README.md

#### Responsibility

README documents Python 3.12 source installation. Requirements are lower-bound declarations without a checked-in lockfile. The manually triggered macOS workflow installs dependencies/PyInstaller and calls a spec and shell script that are absent.

#### Relevant contract

A clean checkout must contain or generate every referenced packaging input. Python/dependency compatibility must be validated on the chosen packaging interpreter; it was not established by this review.

#### Sources

##### Item 1

###### Path

requirements.txt

###### Lines

1. 1

2. 21

###### Label

requirements.txt

###### Url

<https://github.com/wwongw21/comic-translate/blob/010048b358cd11e625fedb4d5843b37fa6368e12/requirements.txt#L1-L21>

##### Item 2

###### Path

.github/workflows/build-macos-dmg.yml

###### Lines

1. 1

2. 45

###### Label

.github/workflows/build-macos-dmg.yml

###### Url

<https://github.com/wwongw21/comic-translate/blob/010048b358cd11e625fedb4d5843b37fa6368e12/.github/workflows/build-macos-dmg.yml#L1-L45>

## Immediate mitigations

### Item 1

#### Finding ids

1. COMIC-1

#### Action

Until repaired, turn off the project autosave setting for important editing sessions, use explicit sequential Save As operations to separate backup files, and reopen the saved project to verify recent edits before closing the working session.

#### Limit

Disabling project_autosave_enabled avoids the regular-project and per-page batch autosave branches identified here, but is not a repair. It reduces automatic protection. A manual save still needs verification; do not treat a clean title/dirty indicator alone as proof that the latest save succeeded. Keep independent backups.

### Item 2

#### Finding ids

1. COMIC-2

#### Action

Avoid queuing multiple state-changing operations. After a worker failure, let outstanding activity settle and reload a verified saved project before continuing important edits.

#### Limit

UI discipline cannot guarantee serialization or stop an already running worker. This is temporary operational guidance, not a correctness control.

### Item 3

#### Finding ids

1. COMIC-3

#### Action

For exports needed before repair, use copied input files with unique ASCII numeric basenames or place potentially colliding pages into separate export groups; verify archive/PDF page count and contents.

#### Limit

The current sanitizer can collapse distinct filenames, and case-insensitive filesystems introduce additional collision risks. A page-count check helps detect loss but does not prevent it. Preserve original source/project files.

### Item 4

#### Finding ids

1. COMIC-4

#### Action

Treat macOS artifacts from the checked-in workflow as unavailable until build inputs are restored and a clean macOS run succeeds.

#### Limit

The review did not execute the workflow or validate any existing downloadable binary. Do not label an artifact verified solely because the workflow file exists.

## Implementation sequence

### Item 1

#### Order

1

#### Finding ids

1. COMIC-1

#### Scope

Guard regular and per-page batch autosave success handling; preserve recovery/dirty state after exceptions. Add meaningful failure/success lifecycle coverage using the existing manual-save failure guard as a local pattern.

#### Dependencies

None recorded.

#### Completion gate

Failed autosave leaves dirty state and existing recovery intact; successful unchanged-revision save cleans once; edits during save remain dirty.

### Item 2

#### Order

2

#### Finding ids

1. COMIC-2

#### Scope

Make queued-operation advancement terminal and exactly once; verify failure callbacks, cancellation and immediate-worker boundaries without changing the unconditional worker finished contract.

#### Dependencies

1. Coordinate callback expectations with COMIC-1; the changes can be separate small commits.

#### Completion gate

Failure of A cannot submit both B and C; B must reach terminal completion before C starts.

### Item 3

#### Order

3

#### Finding ids

1. COMIC-3

#### Scope

Generate deterministic unique ordered names per export group and cover normalized/case/Unicode basename collisions.

#### Dependencies

None recorded.

#### Completion gate

Every successfully rendered page has its own output entry and preserves group order across ZIP/CBZ, CB7 and PDF.

### Item 4

#### Order

4

#### Finding ids

1. COMIC-4

#### Scope

Restore checked-in or explicitly generated packaging inputs, settle the build interpreter/dependency set and validate one clean macOS package.

#### Dependencies

1. Can restore build infrastructure in parallel; validate final distributed artifact after the runtime repairs are included.

#### Completion gate

Clean checkout builds the expected DMG; packaged application starts and passes targeted save/export failure checks.

## Findings and implementation handoff

### COMIC-1 High: Failed autosave deletes recovery and marks the project saved

**Status:** OPEN. [Pinned source](https://github.com/wwongw21/comic-translate/blob/010048b358cd11e625fedb4d5843b37fa6368e12/app/controllers/projects.py#L417).

#### Evidence classification

Confirmed through the validation described below

#### Observed mechanism

GenericWorker.run emits error on exception then always emits finished (app/thread_worker.py:33-37). autosave_project.on_error logs failure but does not preserve a failure flag; on_finished clears the recovery checkpoint and calls set_project_clean whenever the revision is unchanged. Per-page batch autosave duplicates this behavior.

#### Impact and scope

A disk-full/permission/serialization failure can leave edits unsaved while removing the recovery copy and suppressing the close-time unsaved-changes prompt. The normal autosave completion path then sees a clean project and schedules no retry. Scope: regular-project or batch autosave; a new edit while saving preserves dirty state and triggers retry, but still deletes recovery. Recovery-only autosave is unaffected. Previously committed project data may survive.

#### Repair direction

Track explicit save success/failure and perform recovery deletion/clean-state updates only on success in both autosave paths; keep dirty state and recovery on failure and surface a retryable error.

#### Verification already obtained

Executed production autosave_project method with minimal UI collaborator stubs. Called its error then finished callbacks in the order guaranteed by GenericWorker; observed recovery deleted and marked clean, with no retry. Full Qt/disk-full UI session not run. Independent second reviewer also used actual worker, task runner and dirty-state methods, a real temporary recovery file and injected ENOSPC; observed dirty=false, recovery_exists=false, retry=false.

#### Evidence classification

Confirmed

#### Implementation status

PROPOSED; not implemented

#### Change surface

##### Item 1

###### Path

app/controllers/projects.py

###### Lines

1. 302

2. 357

###### Label

Per-page batch autosave

###### Url

<https://github.com/wwongw21/comic-translate/blob/010048b358cd11e625fedb4d5843b37fa6368e12/app/controllers/projects.py#L302-L357>

##### Item 2

###### Path

app/controllers/projects.py

###### Lines

1. 375

2. 431

###### Label

Regular/recovery autosave

###### Url

<https://github.com/wwongw21/comic-translate/blob/010048b358cd11e625fedb4d5843b37fa6368e12/app/controllers/projects.py#L375-L431>

##### Item 3

###### Path

app/controllers/projects.py

###### Lines

1. 1080

2. 1122

###### Label

Existing manual-save failure guard

###### Url

<https://github.com/wwongw21/comic-translate/blob/010048b358cd11e625fedb4d5843b37fa6368e12/app/controllers/projects.py#L1080-L1122>

##### Item 4

###### Path

app/thread_worker.py

###### Lines

1. 33

2. 37

###### Label

Worker terminal signal contract

###### Url

<https://github.com/wwongw21/comic-translate/blob/010048b358cd11e625fedb4d5843b37fa6368e12/app/thread_worker.py#L33-L37>

##### Item 5

###### Path

controller.py

###### Lines

1. 373

2. 395

###### Label

Dirty-state ownership

###### Url

<https://github.com/wwongw21/comic-translate/blob/010048b358cd11e625fedb4d5843b37fa6368e12/controller.py#L373-L395>

##### Item 6

###### Path

controller.py

###### Lines

1. 848

2. 878

###### Label

Close-time prompt

###### Url

<https://github.com/wwongw21/comic-translate/blob/010048b358cd11e625fedb4d5843b37fa6368e12/controller.py#L848-L878>

#### Repair steps

1. Keep GenericWorker.finished unconditional; it is needed for terminal cleanup on both success and failure. Add explicit per-attempt save outcome tracking to both autosave paths, using the existing guarded manual-save pattern or an equally clear success/error separation.

2. Perform clear_recovery_checkpoint, recent-project success bookkeeping and set_project_clean only after the write succeeds. Keep the saved revision comparison so a new edit during a successful save remains dirty.

3. Make pending-worker/reference cleanup run once regardless of outcome. Keep failure visible and recovery intact. Define a bounded or explicit retry policy rather than silently clearing the error state or spinning on persistent disk failure.

4. Cover per-page batch autosaves as well as ordinary timer/debounced autosaves; their direct worker scheduling differs and is easy to miss.

#### Invariants

1. Failure never removes a previously valid recovery checkpoint and never clears unsaved state.

2. Success can clean only the dirty revision represented by the completed save.

3. Every save attempt releases its pending/reference state exactly once.

4. Recovery-only checkpoints remain isolated from regular-project success cleanup.

#### Acceptance criteria

1. On unchanged-revision regular save failure, has_unsaved_changes remains true, an existing recovery file remains present and close still offers the unsaved-changes prompt.

2. On changed-revision failure, recovery remains present and new edits remain dirty; retry behavior is explicit.

3. On successful unchanged-revision save, clean-state/recovery success cleanup happens once; on successful changed-revision save, the current project remains dirty.

4. The same expectations hold for per-page batch autosave, and a failed save does not cause an endless immediate retry loop.

#### Regression cases

1. Injected ENOSPC, permission failure and serialization exception before successful save completion.

2. Success, failure, retry success and a new edit while the save is in flight.

3. Regular project, recovery-only checkpoint and per-page batch paths.

4. A queued save followed by another operation, checking error then finished delivery and bookkeeping once.

#### Risks and rollback

1. Changing the meaning or emission of GenericWorker.finished would affect every caller; prefer a local autosave correction.

2. Retry storms or duplicate completion cleanup could create new state races; test pending flags and direct batch worker references.

3. Rollback a failing repair commit or binary while retaining separate project/recovery backups. Reverting code cannot restore a recovery file already deleted by the baseline defect.

#### Existing validation refs

1. Primary defect reproduction

2. Independent autosave challenge

#### Scope caveats

1. The false-clean result requires regular-project autosave and an unchanged dirty revision; edited-during-save failures still delete recovery but preserve dirty state.

2. Recovery-only autosave is unaffected by the destructive clean branch.

3. Previously committed SQLite project data may survive; the demonstrated risk is latest unsaved edits and recovery protection, not guaranteed loss of every historical project byte.

### COMIC-2 Medium: One failed queue operation starts two following operations together

**Status:** OPEN. [Pinned source](https://github.com/wwongw21/comic-translate/blob/010048b358cd11e625fedb4d5843b37fa6368e12/app/controllers/task_runner.py#L69).

#### Evidence classification

Confirmed through the validation described below

#### Observed mechanism

Both enhanced_error_callback and enhanced_finished_callback schedule _process_next_operation. GenericWorker emits both error and finished for a failed callback, so two pending operations are popped and submitted to the threadpool before either has completed.

#### Impact and scope

The serialization guarantee breaks after an ordinary file/model/network error. Image loads, project saves, and processing jobs can then share mutable state concurrently, and current_worker tracks only the most recently started job.

#### Repair direction

Advance the queue exactly once, normally from finished; let error only report the failure. Ensure cancellation does not reset processing state until the active worker actually completes.

#### Verification already obtained

Ran the real GenericWorker and TaskRunnerController classes using deterministic Signal/QTimer shims. Enqueued failing A followed by B and C; after processing A error/finished callbacks, B and C were both submitted while neither had run. Qt event-loop integration not run.

#### Evidence classification

Confirmed

#### Implementation status

PROPOSED; not implemented

#### Change surface

##### Item 1

###### Path

app/controllers/task_runner.py

###### Lines

1. 61

2. 90

###### Label

Queue completion/error handlers

###### Url

<https://github.com/wwongw21/comic-translate/blob/010048b358cd11e625fedb4d5843b37fa6368e12/app/controllers/task_runner.py#L61-L90>

##### Item 2

###### Path

app/controllers/task_runner.py

###### Lines

1. 92

2. 120

###### Label

Signal dispatch

###### Url

<https://github.com/wwongw21/comic-translate/blob/010048b358cd11e625fedb4d5843b37fa6368e12/app/controllers/task_runner.py#L92-L120>

##### Item 3

###### Path

app/controllers/task_runner.py

###### Lines

1. 123

2. 170

###### Label

Immediate and cancellation boundaries

###### Url

<https://github.com/wwongw21/comic-translate/blob/010048b358cd11e625fedb4d5843b37fa6368e12/app/controllers/task_runner.py#L123-L170>

##### Item 4

###### Path

app/thread_worker.py

###### Lines

1. 19

2. 40

###### Label

Worker result/error/finished emission

###### Url

<https://github.com/wwongw21/comic-translate/blob/010048b358cd11e625fedb4d5843b37fa6368e12/app/thread_worker.py#L19-L40>

#### Repair steps

1. Choose one terminal path to advance the normal queue, normally enhanced_finished_callback. Remove queue advancement from the error-reporting callback.

2. Ensure user result/error/finished callback exceptions cannot accidentally create duplicate advancement or permanently strand queued work; preserve error reporting while terminal housekeeping is deterministic.

3. Test cancellation and clear_operation_queue against the active worker lifecycle. Do not assume GenericWorker.cancel immediately stops its callable; it mainly suppresses result delivery.

4. Preserve run_threaded_immediate and direct batch autosave semantics deliberately. Do not serialize all workers globally as an accidental side effect of repairing the normal queue.

#### Invariants

1. At most one normal queued operation is active until it reaches terminal completion.

2. One terminal operation advances the queue at most once.

3. Failure reports its error and still allows the next queued operation to run once.

4. Intentional immediate/direct worker paths remain explicit exceptions rather than being confused with normal queue serialization.

#### Acceptance criteria

1. For failing A followed by B and C, only B is submitted after A terminates; C is submitted only after B terminates.

2. The same order holds when A succeeds or is cancelled.

3. An empty queue transitions to idle once, and a subsequently enqueued job runs once.

4. Callback failures and cancellation do not cause duplicate starts; any policy for handling callback exceptions is documented and exercised.

#### Regression cases

1. Success A -> B -> C and failure A -> B -> C with observable start/finish barriers.

2. Failure in B, queue empty after failure, enqueue after the queue drains.

3. Cancellation while a callable is still running, queue clear, and enqueue during cancellation.

4. Immediate worker launched while queued work is active; assert the intended behavior without changing it incidentally.

#### Risks and rollback

1. A fix at GenericWorker emission would disturb valid finally/cleanup behavior in many callers; prefer one queue owner for advancement.

2. Real Qt signal delivery and timer reentrancy still need integration coverage; shimmed tests establish current logic but cannot prove all event-loop timing.

3. Keep the patch small enough to revert independently. During rollback avoid concurrent editing/saves and reopen a verified saved project before continuing critical work.

#### Existing validation refs

1. Primary defect reproduction

#### Scope caveats

1. The demonstrated failure requires at least two later queued jobs. With fewer jobs the duplicate callbacks can still disturb queue idle state, but that additional scenario was not the reported reproduction.

2. Specific data corruption was not demonstrated; concurrency and a current_worker pointer that tracks only the last submission were demonstrated/traced.

### COMIC-3 Medium: Distinct page filenames collide during export and silently lose pages

**Status:** OPEN. [Pinned source](https://github.com/wwongw21/comic-translate/blob/010048b358cd11e625fedb4d5843b37fa6368e12/app/controllers/projects.py#L827).

#### Evidence classification

Confirmed through the validation described below

#### Observed mechanism

_build_export_page_name sanitizes all non-ASCII or special characters but ignores page_number unless the resulting stem is empty. a b.png and a?b.png both map to a_b.png. save_and_make_worker saves them into the same group directory without collision detection, overwriting the first page before make() packs the directory.

#### Impact and scope

The generated archive/PDF silently omits pages. Distinct original basenames also bypass the duplicate-basename partition prompt, so this affects ordinary international/special-character filenames even when originals are unique.

#### Repair direction

Generate unique ordered names within every export group, for example prefix each sanitized filename with its page_number; preserve every page regardless of basename or case collisions.

#### Verification already obtained

Executed the real export naming and save_and_make_worker methods with a minimal file-writing renderer. Two distinct input pages produced only one a_b.png containing the second page at archive creation time.

#### Evidence classification

Confirmed

#### Implementation status

PROPOSED; not implemented

#### Change surface

##### Item 1

###### Path

app/controllers/projects.py

###### Lines

1. 802

2. 811

###### Label

Partition prompt compares original basenames

###### Url

<https://github.com/wwongw21/comic-translate/blob/010048b358cd11e625fedb4d5843b37fa6368e12/app/controllers/projects.py#L802-L811>

##### Item 2

###### Path

app/controllers/projects.py

###### Lines

1. 827

2. 836

###### Label

Page filename generation

###### Url

<https://github.com/wwongw21/comic-translate/blob/010048b358cd11e625fedb4d5843b37fa6368e12/app/controllers/projects.py#L827-L836>

##### Item 3

###### Path

app/controllers/projects.py

###### Lines

1. 900

2. 927

###### Label

Rendering and packaging loop

###### Url

<https://github.com/wwongw21/comic-translate/blob/010048b358cd11e625fedb4d5843b37fa6368e12/app/controllers/projects.py#L900-L927>

##### Item 4

###### Path

modules/utils/archives.py

###### Lines

1. 437

2. 470

###### Label

Archive and PDF enumeration

###### Url

<https://github.com/wwongw21/comic-translate/blob/010048b358cd11e625fedb4d5843b37fa6368e12/modules/utils/archives.py#L437-L470>

#### Repair steps

1. Make output names unique within each export group, preferably by always prefixing a stable zero-padded page ordinal and retaining a sanitized readable suffix. Use sufficient ordinal width for the group size.

2. Keep path creation inside the group directory, preserve a supported extension and make output ordering deterministic. If preserving basenames exactly is a requirement, use an explicit collision allocator instead; do not rely on the partition dialog.

3. Use the resolved output name for the renderer and every downstream reference. Add coverage proving distinct page payloads survive through directory staging and packaging.

4. Keep original page identity and project paths unchanged; this repair concerns generated export entries.

#### Invariants

1. Distinct successfully rendered pages in one group never share an output path, including after sanitization or case normalization.

2. Export order corresponds to the group page order, including PDF natural-sort behavior.

3. Grouping and naming do not mutate original inputs or project identity.

#### Acceptance criteria

1. Two pages with colliding sanitized stems produce two entries with distinct expected contents.

2. Duplicate basenames from separate folders, Unicode-only names, case variants and names stripped to fallback stems remain distinct.

3. Each export group has the expected number and order of rendered pages in real ZIP/CBZ, CB7 and PDF output.

4. Ordinary filenames, text/patch rendering and existing grouping behavior still work.

#### Regression cases

1. Baseline pair a b.png and a?b.png on a filesystem that supports them; portable cross-platform pair a b.png and a+b.png.

2. Same basename from different directories and case-only differences on a case-insensitive filesystem.

3. Non-Latin names that normalize identically or to an empty stem; page numbers beyond the default padding width.

4. Multiple chapter groups and a single group; mixed supported image extensions; real archive entry and PDF page integrity.

#### Risks and rollback

1. Generated export filenames may change, which can affect external reading/bookmark workflows; call out the new convention in release notes.

2. A naive numeric prefix can order incorrectly at high page counts unless the width or sort behavior is defined.

3. Rollback is limited to generated output naming. Keep source projects and generate exports to separate files so an incorrect new artifact can be discarded and regenerated. Already overwritten staging pages cannot be recovered from the old exported archive alone.

#### Existing validation refs

1. Primary defect reproduction

#### Scope caveats

1. The demonstrated loss is in the generated export, not deletion of original input images.

2. The review used a minimal renderer and intercepted packaging input; actual PDF/CB7 rendering and file-format integrity were not tested.

### COMIC-4 Medium: The only macOS packaging workflow references files absent from the repository

**Status:** OPEN. [Pinned source](https://github.com/wwongw21/comic-translate/blob/010048b358cd11e625fedb4d5843b37fa6368e12/.github/workflows/build-macos-dmg.yml#L32).

#### Evidence classification

Confirmed through the validation described below

#### Observed mechanism

The workflow runs pyinstaller ct-mac.spec and chmod +x builddmg.sh / ./builddmg.sh, but neither ct-mac.spec nor builddmg.sh exists in the pinned checkout or git ls-files. There is no preceding step generating either.

#### Impact and scope

The workflow cannot produce the advertised macOS DMG from a clean checkout, regardless of dependency installation success.

#### Repair direction

Check in the intended PyInstaller spec and DMG build script or change workflow commands to a complete checked-in build entry point; validate one clean macOS Actions run.

#### Verification already obtained

Confirmed both files absent via filesystem checks and git ls-files; inspected full workflow. GitHub Actions/macOS build not executed.

#### Evidence classification

Confirmed

#### Implementation status

PROPOSED; not implemented

#### Change surface

##### Item 1

###### Path

.github/workflows/build-macos-dmg.yml

###### Lines

1. 8

2. 45

###### Label

Clean macOS build steps

###### Url

<https://github.com/wwongw21/comic-translate/blob/010048b358cd11e625fedb4d5843b37fa6368e12/.github/workflows/build-macos-dmg.yml#L8-L45>

##### Item 2

###### Path

README.md

###### Lines

1. 92

2. 126

###### Label

Documented Python source-install setup

###### Url

<https://github.com/wwongw21/comic-translate/blob/010048b358cd11e625fedb4d5843b37fa6368e12/README.md#L92-L126>

#### Repair steps

1. Locate or recreate the intended PyInstaller spec and DMG script under version control, or replace both workflow invocations with a complete checked-in build entry point. No missing script/spec was located in this fork.

2. Ensure every icon/resource/hidden import required by the GUI and model/runtime modules is included, and that the build does not depend on untracked developer-machine files.

3. Choose a supported build interpreter and tested dependency resolution, reconciling the README Python 3.12 setup with the workflow Python 3.14.5 request through evidence rather than assuming compatibility.

4. Run a clean macOS workflow and validate the actual installed/launched app plus targeted runtime repairs before considering release packaging restored.

#### Invariants

1. Every file directly invoked by the workflow exists in the checkout or is generated explicitly by an earlier reproducible step.

2. The expected dist/Comic Translate.dmg is produced from the reviewed commit without untracked local inputs.

3. A built artifact includes required resources and can launch on the intended macOS target.

#### Acceptance criteria

1. Clean checkout can complete dependency installation, PyInstaller packaging, DMG creation and artifact upload.

2. The workflow uses an explicit validated interpreter and retains logs/artifact provenance.

3. Opening the DMG and launching the packaged app succeeds; save/export regression checks pass in the packaged environment.

#### Regression cases

1. Fresh macOS runner with empty caches and no developer-local packaging files.

2. Resource/icon/Qt plugin discovery; cold application launch and open existing project.

3. Failed-save dirty/recovery behavior and representative export behavior in the packaged app.

4. Architecture/deployment target combinations explicitly supported by the maintainer; no untested compatibility claim.

#### Risks and rollback

1. Restoring missing inputs may expose further packaging or dependency compatibility failures; this review did not establish a complete correct spec.

2. Packaging can pass while required lazy imports/resources are absent; artifact launch and real workflows are necessary.

3. If the candidate package fails, withhold it or revert to a previously independently verified artifact. This review did not establish that any existing published artifact is verified.

#### Existing validation refs

1. Tracked packaging inputs and test inventory

#### Scope caveats

1. Missing referenced files are confirmed statically; no GitHub Actions dispatch or macOS build was run.

2. The Python-version difference is a validation task, not a separate confirmed defect.

## Reproductions

### Item 1

#### Name

Primary defect reproductions and Python syntax coverage

#### Command

```
python /workspace/review/comic_repro.py
```

#### Working directory

Any directory; the script reads /workspace/repos/comic-translate by absolute path.

#### Prerequisites

1. Python 3.12 was used in the review environment.

2. Pinned checkout at /workspace/repos/comic-translate and the supplied evidence script at /workspace/review/comic_repro.py.

3. Standard library only; the script replaces Qt signals/timers with deterministic shims and extracts selected production methods. It does not require PySide6, models, paid credentials or network access.

#### Observed status

RUN; all defect assertions passed.

#### Observed results

1. QUEUE REPRO: a failed first job starts B and C before either finishes; active pending workers = 2.

2. EXPORT REPRO: two distinct input pages produce only a_b.png containing the second page at packaging time.

3. BUILD REPRO: ct-mac.spec and builddmg.sh are missing.

4. SYNTAX: compiled all 285 Python files in memory without writing bytecode. A SyntaxWarning appeared for an existing invalid escape sequence in the vendored Pororo utility.

5. AUTOSAVE REPRO: failed save caused recovery deleted and marked clean; no retry was scheduled.

#### What it proves

Production callback, naming and export-worker control flow under deterministic collaborators; missing packaging inputs; source syntax validity.

#### What it does not prove

Actual Qt delivery/integration, rendering fidelity, real disk exhaustion, model inference, paid API behavior or a successful macOS build.

#### Future use

These assertions intentionally confirm current defects. After repair, convert them into regression checks asserting the corrected behavior; a raw assertion failure after a fix may be expected and is not by itself a regression.

### Item 2

#### Name

Independent autosave challenge

#### Command

```
python /workspace/review/comic_autosave_challenge.py
```

#### Working directory

Any directory; the script reads the pinned checkout by absolute path.

#### Prerequisites

1. Python standard library.

2. The pinned checkout and supplied script; the script creates temporary recovery files under /workspace/review.

3. No PySide6 or models required; Qt Signal/QTimer behavior is shimmed.

#### Observed status

RUN by an independent reviewer; all assertions passed.

#### Observed results

##### Item 1

###### Case

Regular project autosave, no new edit during save, injected OSError(28)

###### Dirty after failure

false

###### Recovery exists after failure

false

###### Retry scheduled

false

##### Item 2

###### Case

Regular project autosave, revision changed during save, injected OSError(28)

###### Dirty after failure

true

###### Recovery exists after failure

false

###### Retry scheduled

true

##### Item 3

###### Case

Recovery-only autosave, injected OSError(28)

###### Dirty after failure

true

###### Recovery exists after failure

true

###### Retry scheduled

false

#### What it proves

Actual GenericWorker, task-runner, autosave, recovery-deletion and dirty-state methods reproduce the scoped failure with a real temporary recovery file. The clean state is not a fake return value.

#### What it does not prove

Live GUI behavior, physical disk-full behavior or full SQLite recovery characteristics. Per-page batch duplication was confirmed by source, not this independent runtime probe.

### Item 3

#### Name

Tracked packaging inputs and test inventory

#### Commands

1. ```
   git -C /workspace/repos/comic-translate ls-files '*spec' '*dmg*' '*test*' 'AGENTS.md'
   ```

2. ```
   git -C /workspace/repos/comic-translate status --short
   ```

#### Prerequisites

1. Git and the pinned checkout.

#### Observed status

RUN.

#### Observed results

1. Only .github/workflows/build-macos-dmg.yml matched the packaging/test/instruction filename search. ct-mac.spec and builddmg.sh are absent.

2. No test directory or tracked test files were found in this checkout.

3. Checkout status was clean; review evidence is stored outside the repository.

#### Limit

No test files found does not prove every external/upstream validation process is absent. The search and checkout describe this fork and commit.

## Release verification

### Item 1

#### Stage

Source and new regression coverage

#### Status

PROPOSED; NOT RUN after repairs because no repairs exist.

#### Steps

1. Review each narrow patch against this pinned baseline and preserve unrelated work.

2. Add focused regression coverage at the stable task/save/export seams described below. There is currently no checked-in test suite to invoke; choose and check in the test setup before naming a standard test command.

3. Rerun Python compilation and the adapted evidence checks. Existing defect-asserting scripts must be updated or interpreted as baseline probes, not treated as passing post-fix gates.

### Item 2

#### Stage

Qt integration and failure handling

#### Status

NOT RUN.

#### Prerequisites

1. A disposable environment with the required PySide6/runtime dependencies installed.

2. Copied comics/projects and a disposable recovery location.

3. Controlled save-failure injection or an unwritable/disposable filesystem; do not test disk exhaustion on real user data.

#### Steps

1. Launch the application from a configured source environment with python comic.py.

2. Edit a page, create a recovery checkpoint, enable project autosave and force a save failure. Confirm the UI remains dirty, existing recovery survives, an understandable retry path is available and closing still warns about unsaved edits.

3. Allow a successful retry; confirm only the revision actually saved is clean. Make a new edit during a save and verify it remains dirty afterward.

4. Run at least three queued operations with the first failing and the next two blocked at observable barriers. Verify the third never starts while the second is still active. Exercise cancellation and clear-queue behavior separately.

5. Perform per-page batch autosave failure/success checks with temporary data; ensure direct workers are released once and failure does not remove recovery.

### Item 3

#### Stage

Real export integrity

#### Status

NOT RUN.

#### Prerequisites

1. Disposable image fixtures with distinguishable page content.

2. Dependencies needed for actual rendering and each chosen archive/PDF format.

#### Steps

1. Export pages whose original basenames normalize to the same stem, including space versus plus, duplicate basenames in different folders, Unicode names and case variants on a case-insensitive filesystem.

2. Inspect ZIP/CBZ and CB7 entry counts and decode/compare the distinguishable pages. For PDF, inspect page count, page order and visible page contents.

3. Verify separate export groups have independent naming scopes and that ordinary filenames, patches, text rendering and webtoon output still work.

4. Do not infer PDF/CB7 success from the mocked-renderer baseline probe.

### Item 4

#### Stage

macOS clean build and distributed app

#### Status

NOT RUN.

#### Prerequisites

1. Restored/generated packaging inputs included in the patch.

2. A clean macOS runner with the explicitly chosen supported Python version and dependency set.

#### Steps

1. Trigger the existing Build macOS DMG workflow from a clean checkout of the repaired commit; preserve its logs and artifact metadata. No workflow dispatch was performed in this review.

2. Confirm PyInstaller discovers all application modules, Qt resources, icons and required runtime data; open the generated DMG and launch the packaged application on the intended macOS target.

3. Repeat targeted save failure, recovery reopen, ordinary page translation and real export checks in the packaged app. Paid/model-dependent checks require configured test credentials/assets and have not been run.

4. Publish only after the artifact corresponds to the reviewed repaired commit and the above release evidence is attached.

## Proposed follow up

### Item 1

#### Item

Establish a small checked-in test harness for worker lifecycle, autosave and export naming.

#### Rationale

No test files were found; the supplied scripts are review evidence outside the repo.

#### Status

PROPOSED; not an implemented change or a claimed existing test suite.

### Item 2

#### Item

Record a tested interpreter/dependency resolution for repeatable packaging.

#### Rationale

README uses Python 3.12 while the workflow requests 3.14.5; requirements are broad minimum bounds. Compatibility was not evaluated.

#### Status

PROPOSED; no compatibility failure is asserted solely from this mismatch.

### Item 3

#### Item

Review task cancellation, immediate jobs and direct batch autosave concurrency with a real Qt event loop after the targeted queue fix.

#### Rationale

These paths deliberately bypass or alter queue state and deserve integration coverage. They were not independently established as additional defects in this handoff.

#### Status

PROPOSED investigation.

## Evidence files

1. /workspace/review/comic.json

2. /workspace/review/comic_repro.py

3. /workspace/review/comic_autosave_challenge.py

4. /workspace/review/comic_independent.json

## Coverage limits

1. No PySide6 installed, so no real GUI session or Qt event loop was exercised. Signal/timer behavior in the queue reproduction uses small deterministic shims.

2. No model downloads, OCR/inpainting inference, paid translation calls, GPU checks, macOS packaging, or live upstream services were run.

3. No dependency vulnerability database scan was run. Dependency requirements are unpinned minimum bounds with no lockfile; reproducibility was reviewed statically.

4. This is broad repository review, not an exhaustive line-by-line audit or formal security scan.

## Change record

Only review/handoff evidence was written outside the repository. No fixes, commits, pull requests, workflow runs or releases were created.

## Delivery and diagnostic files

### Destination repository

wwongw21/comic-translate

### Status

All findings remain OPEN; documentation transfer only.

### Portable evidence

This JSON retains the complete repository-specific handoff. Historical /workspace paths are evidence references and prerequisites, not portable hyperlinks. Applicable repository-specific diagnostics are included alongside the report.

### Diagnostics included

1. comic_repro.py

2. comic_autosave_challenge.py

3. comic_independent.json

### Not included

Original environments, model weights, user data and complete source snapshots are not included. Clone the pinned source and follow the recorded prerequisites. Bug-demonstration scripts intentionally assert pre-fix behavior; they are not a post-fix passing suite.

- [comic_repro.py](diagnostics/comic_repro.py)
- [comic_autosave_challenge.py](diagnostics/comic_autosave_challenge.py)
- [comic_independent.json](diagnostics/comic_independent.json)

## Remaining review limits

1. No PySide6 installed, so no real GUI session or Qt event loop was exercised. Signal/timer behavior in the queue reproduction uses small deterministic shims.

2. No model downloads, OCR/inpainting inference, paid translation calls, GPU checks, macOS packaging, or live upstream services were run.

3. No dependency vulnerability database scan was run. Dependency requirements are unpinned minimum bounds with no lockfile; reproducibility was reviewed statically.

4. This is broad repository review, not an exhaustive line-by-line audit or formal security scan.

