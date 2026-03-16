# Implementation Plan

- [ ] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - Duplicate Frames Sent to AI Pipeline
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate the bug exists
  - **Scoped PBT Approach**: Scope the property to concrete failing cases - mock VideoCapture that returns identical frames repeatedly
  - Test that when cap.read() returns the same frame data consecutively, the unfixed grab_frames() publishes duplicate frames to ai.frame.lpr queue
  - Create mock VideoCapture that returns ret=True but same frame buffer for 10 consecutive reads
  - Verify that 10 messages are published to the AI queue (all with identical frame data)
  - Run test on UNFIXED code in backend-fastapi/workers/frame_grabber/worker/service.py
  - **EXPECTED OUTCOME**: Test FAILS (this is correct - it proves the bug exists)
  - Document counterexamples found: "grab_frames() published 10 identical frames to ai.frame.lpr when cap.read() returned same frame buffer repeatedly"
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [ ] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Non-Duplicate Frame Behavior
  - **IMPORTANT**: Follow observation-first methodology
  - Observe behavior on UNFIXED code for non-buggy inputs (different consecutive frames)
  - Test Case 1: Normal frame sequence - generate random sequences of different frames, observe that each frame is published to queues
  - Test Case 2: Thumbnail updates - observe that thumbnails update every 30 frames regardless of frame content
  - Test Case 3: ROI routing - observe that messages route to correct queues (ai.frame vs ai.frame.lpr) based on ROI type
  - Test Case 4: Frame storage - observe that all frames are saved to disk with correct naming format
  - Write property-based tests capturing observed behavior patterns from Preservation Requirements
  - Property-based testing generates many test cases for stronger guarantees
  - Run tests on UNFIXED code in backend-fastapi/workers/frame_grabber/worker/service.py
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

- [ ] 3. Fix for duplicate frame detection in frame_grabber

  - [ ] 3.1 Implement frame hash tracking and duplicate detection
    - Add previous_frame_hash variable to track last processed frame hash for each camera (initialize to None)
    - Add duplicate_count to camera_data dictionary for monitoring
    - Implement compute_frame_hash() function using fast downsampled approach (resize to 64x64, hash bytes)
    - After successful cap.read(), compute current frame hash and compare with previous_frame_hash
    - If hashes match (duplicate detected), increment duplicate_count and skip AI pipeline publishing
    - If hashes differ, update previous_frame_hash and proceed with normal processing
    - Ensure thumbnail generation continues before duplicate check (thumbnails update regardless)
    - Ensure frame storage to disk continues before duplicate check
    - Add duplicate count to periodic logging output
    - _Bug_Condition: isBugCondition(current_frame, previous_frame) where frames_are_identical(current_frame, previous_frame) AND frame_sent_to_ai_pipeline(current_frame)_
    - _Expected_Behavior: For duplicate frames (same hash), skip publishing to ai.frame and ai.frame.lpr queues, increment duplicate_count_
    - _Preservation: Thumbnail generation, ROI routing, frame storage, and message publishing for non-duplicate frames must remain unchanged_
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

  - [ ] 3.2 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Only New Frames Sent to AI Pipeline
    - **IMPORTANT**: Re-run the SAME test from task 1 - do NOT write a new test
    - The test from task 1 encodes the expected behavior
    - When this test passes, it confirms the expected behavior is satisfied
    - Run bug condition exploration test from step 1
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed - duplicate frames are now skipped)
    - Verify that when cap.read() returns identical frames, only the first frame is published to AI queues
    - Verify that duplicate_count increments for each skipped duplicate frame
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [ ] 3.3 Verify preservation tests still pass
    - **Property 2: Preservation** - Non-Duplicate Frame Behavior
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run preservation property tests from step 2
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Confirm all tests still pass after fix (no regressions in thumbnail updates, ROI routing, frame storage, or message publishing for different frames)

- [ ] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.
