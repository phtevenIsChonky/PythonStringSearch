import os
import re
import datetime
import gzip
import traceback
import concurrent.futures
from tqdm import tqdm # Import tqdm

# --- Configuration ---
# Directory to search for files.
target_directory = r"C:\Your\Log\Directory" # CHANGE THIS to the root directory you want to search.
# Full path for the output file where results will be saved.
output_file_path = r"C:\Your\Output\found_strings_with_context.txt" # CHANGE THIS to your desired output file path.
# Set to True to search subdirectories recursively, False for just the top-level target_directory.
include_subdirectories = True

# Define file extensions to IGNORE.
# Files with these extensions will be skipped entirely.
# Ensure extensions start with a dot and are in lowercase (e.g., ".exe", ".tmp").
ignore_extensions = [
    ".cur",       # Example: Windows cursor files (typically binary)
    ".exe",       # Example: Executable files
    ".dll",       # Example: Library files
    ".journal",   # Example: If these are binary systemd journals on your system
]

# List of specific strings to search for in the files.
strings_to_search = [
    "edge-services-qa.stgedge.com", 
    "ERROR_CODE_XYZ",               
    "UserLoginFailedEvent",         
    "critical system alert",
    "testtest.com"                  
]

# Define a threshold for "massive" plain text files (in bytes).
MASSIVE_PLAIN_TEXT_THRESHOLD_BYTES = 500 * 1024 * 1024


# --- Worker Function for Parallel Processing ---
# (process_file_worker function remains the same as the last version)
def process_file_worker(file_path, compiled_patterns_with_originals):
    """
    Processes a single file: opens/decompresses, reads lines, and searches for specified strings.
    For massive plain text files, it reads line by line to save memory.
    """
    # This print indicates which file a worker is starting on.
    # In parallel execution, output from different workers might interleave with tqdm.
    # tqdm typically prints to stderr, print() to stdout.
    # print(f"Worker starting on: {file_path}") # Keep this if you want per-worker start, or remove for cleaner tqdm output

    found_results_for_this_file = []
    is_gz_file = file_path.lower().endswith(".gz")
    search_was_performed_on_actual_content = False 

    try:
        opened_file_stream = None 
        lines_from_small_file = None 

        if is_gz_file:
            try:
                opened_file_stream = gzip.open(file_path, 'rt', encoding='utf-8', errors='ignore')
            except gzip.BadGzipFile as e_bad_gz:
                return file_path, [], f"Corrupted/Invalid .gz file: {e_bad_gz}"
            except Exception as e_gz: 
                return file_path, [], f"Error reading gzipped file: {e_gz}"
        else:
            try:
                file_size = os.path.getsize(file_path)
                if file_size <= MASSIVE_PLAIN_TEXT_THRESHOLD_BYTES:
                    lines_to_process_directly = []
                    try: 
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f_text:
                            lines_to_process_directly = f_text.readlines()
                    except UnicodeDecodeError: 
                        # print(f"Info (worker): UTF-8 decode failed for small file {file_path}, trying Latin-1.") # Can be noisy with tqdm
                        try:
                            with open(file_path, 'r', encoding='latin-1', errors='ignore') as f_text_latin:
                                lines_to_process_directly = f_text_latin.readlines()
                        except Exception as e_small_latin: 
                            return file_path, [], f"Error opening/reading small text file with Latin-1: {e_small_latin}"
                    except Exception as e_small_utf8: 
                        return file_path, [], f"Error opening/reading small text file with UTF-8: {e_small_utf8}"
                    
                    if lines_to_process_directly: 
                        search_was_performed_on_actual_content = True 
                        for line_number, line_content in enumerate(lines_to_process_directly, 1):
                            for original_string, compiled_pattern in compiled_patterns_with_originals:
                                if compiled_pattern.search(line_content):
                                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    result = (f"[{timestamp}] File: {file_path} | Line: {line_number} | "
                                              f"Found String: \"{original_string}\" | Context: {line_content.strip()}")
                                    found_results_for_this_file.append(result)
                    
                else: 
                    # print(f"Info (worker): File '{file_path}' is massive (>{MASSIVE_PLAIN_TEXT_THRESHOLD_BYTES / (1024*1024):.0f}MB), will read line-by-line.") # Can be noisy
                    opened_file_stream = open(file_path, 'r', encoding='utf-8', errors='ignore')

            except Exception as e_open_prepare: 
                return file_path, [], f"Error preparing plain text file for reading: {e_open_prepare}"
        
        if opened_file_stream:
            try:
                lines_iterated_from_stream = 0
                for line_number, line_content in enumerate(opened_file_stream, 1):
                    if lines_iterated_from_stream == 0: 
                        search_was_performed_on_actual_content = True
                    lines_iterated_from_stream += 1
                    
                    for original_string, compiled_pattern in compiled_patterns_with_originals:
                        if compiled_pattern.search(line_content):
                            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            result = (
                                f"[{timestamp}] File: {file_path} | Line: {line_number} | "
                                f"Found String: \"{original_string}\" | Context: {line_content.strip()}"
                            )
                            found_results_for_this_file.append(result)
                # if lines_iterated_from_stream == 0 and os.path.getsize(file_path) > 0: 
                #     print(f"Info (worker): Stream for '{file_path}' yielded no lines.") # Can be noisy

            except UnicodeDecodeError: 
                if not is_gz_file: 
                    try:
                        if opened_file_stream and not opened_file_stream.closed:
                           opened_file_stream.close() 
                        # print(f"Info (worker): Retrying massive plain text file '{file_path}' with Latin-1 encoding.") # Can be noisy
                        with open(file_path, 'r', encoding='latin-1', errors='ignore') as f_latin_stream:
                            lines_iterated_from_latin_stream = 0
                            for line_number, line_content in enumerate(f_latin_stream, 1):
                                if lines_iterated_from_latin_stream == 0:
                                    search_was_performed_on_actual_content = True
                                lines_iterated_from_latin_stream +=1
                                for original_string, compiled_pattern in compiled_patterns_with_originals:
                                    if compiled_pattern.search(line_content):
                                        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                        result = (f"[{timestamp}] File: {file_path} | Line: {line_number} | "
                                                  f"Found String: \"{original_string}\" | Context: {line_content.strip()}")
                                        found_results_for_this_file.append(result)
                            # if lines_iterated_from_latin_stream == 0 and os.path.getsize(file_path) > 0:
                            #     print(f"Info (worker): Latin-1 stream for '{file_path}' yielded no lines.") # Can be noisy
                    except Exception as e_latin_stream: 
                        return file_path, found_results_for_this_file, f"Error in latin-1 stream for massive plain text: {e_latin_stream}"
            except Exception as e_stream_read: 
                 return file_path, found_results_for_this_file, f"Error reading stream for {file_path}: {e_stream_read}"
            finally:
                if opened_file_stream and not opened_file_stream.closed: 
                    opened_file_stream.close()
        
        file_actually_has_size = os.path.getsize(file_path) > 0
        if file_actually_has_size and not found_results_for_this_file:
            if search_was_performed_on_actual_content:
                # This specific print might still be useful if you want to know about files searched with no hits.
                # However, it can be very noisy with tqdm if many files are like this.
                # Consider commenting it out if the tqdm progress is enough.
                # print(f"Info (worker): File '{file_path}' was read and searched, but no target strings were found.")
                pass 
            else:
                # print(f"Info (worker): File '{file_path}' has size but yielded no searchable text lines.") # Can be noisy
                pass
        # elif not file_actually_has_size and not found_results_for_this_file:
        #      print(f"Info (worker): File '{file_path}' is empty (0 bytes).") # Can be noisy

        return file_path, found_results_for_this_file, None 

    except Exception as e_outer_worker: 
        return file_path, [], f"Unexpected error in worker for file '{file_path}': {e_outer_worker} \n{traceback.format_exc()}"


# --- Main Script Logic ---
def main_script_logic():
    if not strings_to_search:
        print("Error: The 'strings_to_search' list is empty. Please add strings to search for.")
        return

    compiled_patterns = []
    for s in strings_to_search:
        try:
            compiled_patterns.append((s, re.compile(re.escape(s), re.IGNORECASE)))
        except re.error as e:
            print(f"Error compiling regex for string '{s}': {e}. Skipping this string.")
    if not compiled_patterns: 
        print("Error: No valid strings to search for after attempting to compile patterns.")
        return

    initial_skipped_file_log = [] 
    print(f"Searching for specific strings in: {target_directory}")
    if include_subdirectories: print("Including subdirectories.")
    else: print("Only searching top-level directory.")
    print(f"Output will be saved to: {output_file_path}")
    if ignore_extensions: print(f"Ignoring files with extensions: {', '.join(ignore_extensions)}")
    print("Strings being searched for (case-insensitive, literal match):")
    for s_original, _ in compiled_patterns: print(f"- {s_original}")
    print("---------------------------------------------------")

    if os.path.exists(output_file_path):
        try:
            os.remove(output_file_path)
            print(f"Cleared existing output file: {output_file_path}")
        except OSError as e:
            print(f"Warning: Could not clear existing output file '{output_file_path}': {e}")
    
    try:
        output_dir_main = os.path.dirname(output_file_path)
        if output_dir_main and not os.path.exists(output_dir_main):
            os.makedirs(output_dir_main)
            print(f"Created output directory: {output_dir_main}")
    except Exception as e_dir_create:
        print(f"CRITICAL ERROR: Could not create output directory '{os.path.dirname(output_file_path)}': {e_dir_create}. Exiting.")
        return

    files_to_consider = [] 
    try:
        if include_subdirectories:
            for root, _, files in os.walk(target_directory):
                for file_name in files:
                    if not os.path.isdir(os.path.join(root, file_name)): 
                        files_to_consider.append(os.path.join(root, file_name))
        else: 
            for file_name in os.listdir(target_directory):
                full_path = os.path.join(target_directory, file_name)
                if os.path.isfile(full_path): 
                    files_to_consider.append(full_path)
    except FileNotFoundError:
        err_msg = f"Target directory '{target_directory}' not found."
        print(f"CRITICAL ERROR: {err_msg}")
        initial_skipped_file_log.append({'path': target_directory, 'reason': err_msg})
    except Exception as e: 
        err_msg = f"Error accessing target directory '{target_directory}': {e}"
        print(f"CRITICAL ERROR: {err_msg}")
        initial_skipped_file_log.append({'path': target_directory, 'reason': err_msg})

    if not files_to_consider:
        if not initial_skipped_file_log: 
             print(f"No files found in '{target_directory}'.")
        if initial_skipped_file_log: log_skipped_files(initial_skipped_file_log, output_file_path)
        return

    print(f"Found {len(files_to_consider)} total file items. Filtering based on ignore_extensions...")

    files_to_process_with_args = []
    for file_path in files_to_consider:
        file_ext = os.path.splitext(file_path)[1].lower()
        if file_ext in ignore_extensions:
            reason = f"Ignored extension: {file_ext}"
            initial_skipped_file_log.append({'path': file_path, 'reason': reason})
            continue 
        files_to_process_with_args.append((file_path, compiled_patterns))

    if not files_to_process_with_args: 
        print(f"No files to process after applying ignore list.")
        if initial_skipped_file_log: log_skipped_files(initial_skipped_file_log, output_file_path)
        return

    print(f"Submitting {len(files_to_process_with_args)} files to worker processes...")

    all_found_result_lines = [] 
    worker_skipped_file_log = [] 
    found_files_set = set() 

    num_workers = max(1, os.cpu_count() - 2 if os.cpu_count() and os.cpu_count() > 2 else 1)
    print(f"Using up to {num_workers} worker processes.")

    # REMOVED: processed_count (tqdm will handle this)
    total_files_to_process = len(files_to_process_with_args)

    with concurrent.futures.ProcessPoolExecutor(max_workers=num_workers) as executor:
        future_to_filepath = {
            executor.submit(process_file_worker, *args_for_worker): args_for_worker[0] 
            for args_for_worker in files_to_process_with_args
        }

        # MODIFIED: Wrap as_completed with tqdm for a progress bar
        for future in tqdm(concurrent.futures.as_completed(future_to_filepath), 
                           total=total_files_to_process, 
                           desc="Processing files", 
                           unit="file",
                           ncols=100): # Optional: set progress bar width
            file_path_processed = future_to_filepath[future]
            # REMOVED: Manual progress printing logic replaced by tqdm

            try:
                _fp_returned, result_lines_from_worker, skip_reason = future.result()
                if skip_reason: 
                    worker_skipped_file_log.append({'path': file_path_processed, 'reason': skip_reason})
                if result_lines_from_worker: 
                    all_found_result_lines.extend(result_lines_from_worker)
                    found_files_set.add(file_path_processed) 
            except Exception as exc: 
                reason = f"Worker process CRASHED or unhandled error for {file_path_processed}: {exc} \n{traceback.format_exc()}"
                # tqdm might interfere with multi-line prints during its active bar updating.
                # For critical errors, it's good to have them print. tqdm handles this by printing above the bar.
                tqdm.write(f"\nERROR: {reason}") # Use tqdm.write to print messages without breaking the bar
                worker_skipped_file_log.append({'path': file_path_processed, 'reason': reason})
    
    # The print("\nAll worker processes finished.") might not be needed as tqdm shows 100%
    # Or you can keep it for explicit confirmation.
    print("All worker processes finished processing tasks.") 
    final_skipped_log = initial_skipped_file_log + worker_skipped_file_log

    # ... (rest of the main_script_logic: writing results, final summary, logging skipped files) ...
    if all_found_result_lines:
        print(f"\nAggregating and writing {len(all_found_result_lines)} found lines to output file...")
        try:
            with open(output_file_path, 'a', encoding='utf-8') as out_f:
                for line in all_found_result_lines:
                    out_f.write(line + "\n")
            print("Finished writing results.")
        except IOError as e_write:
            print(f"CRITICAL ERROR: Could not write results to '{output_file_path}': {e_write}")

    print("---------------------------------------------------")
    print("Search complete!")
    if all_found_result_lines:
        print(f"Results saved to: {output_file_path}")
        print(f"Total matching lines found: {len(all_found_result_lines)} in {len(found_files_set)} file(s).")
    else:
        print("No occurrences of the specified strings were found in the searched files.")
    
    if final_skipped_log:
        log_skipped_files(final_skipped_log, output_file_path)


# (log_skipped_files function remains the same)
def log_skipped_files(skipped_records, output_file_path_param):
    if not skipped_records:
        return
    
    skipped_header = "\n--- Files Skipped or Errored During Processing ---"
    print(skipped_header) # Print to console
    # Use tqdm.write for messages that should appear above the bar if it were still active
    # However, this function is called after the main tqdm loop.
    
    try:
        output_dir = os.path.dirname(output_file_path_param)
        if output_dir and not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except Exception:
                pass 

        with open(output_file_path_param, 'a', encoding='utf-8') as out_f:
            out_f.write(skipped_header + "\n")
            for record in skipped_records:
                log_entry = f"File: {record['path']} | Reason: {record['reason']}"
                print(log_entry) 
                out_f.write(log_entry + "\n")
    except IOError as e:
        print(f"Error: Could not write skipped files log to '{output_file_path_param}': {e}")


# This guard is crucial for multiprocessing to work correctly on some platforms (like Windows).
if __name__ == "__main__":
    script_start_time = datetime.datetime.now()
    print(f"Script started at: {script_start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        main_script_logic()
    except Exception as e: 
        print("---------------------------------------------------")
        print("AN UNEXPECTED CRITICAL ERROR OCCURRED IN THE SCRIPT (MAIN BLOCK):")
        print(str(e)); print("---------------------------------------------------")
        traceback.print_exc()
    finally:
        script_end_time = datetime.datetime.now()
        print(f"Script finished at: {script_end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Total execution time: {script_end_time - script_start_time}")

        # --- Attempt to open the output file ---
        # Check if the output file path is defined and the file actually exists
        if 'output_file_path' in globals() and os.path.exists(output_file_path):
            print(f"\nAttempting to open output file: {output_file_path}")
            try:
                os.startfile(output_file_path) # This is Windows-specific
            except AttributeError:
                # This might happen if 'os.startfile' is not available (e.g., not on Windows)
                # or if the script is run in an environment where it's restricted.
                print(f"Info: 'os.startfile()' not available on this system or failed. Please open the file manually.")
                # You could add a fallback for other systems if needed, e.g., using webbrowser
                # import webbrowser
                # try:
                #     webbrowser.open(os.path.realpath(output_file_path))
                # except Exception as e_wb:
                #      print(f"Info: Could not open file with webbrowser: {e_wb}")
            except Exception as e_startfile:
                print(f"Error: Could not automatically open the output file '{output_file_path}': {e_startfile}")
        elif 'output_file_path' in globals():
            print(f"\nInfo: Output file '{output_file_path}' not found or not created. Cannot open it automatically.")
        # --- End of attempting to open the output file ---

        print("\n--- Script execution finished or was interrupted ---")
        input("Press Enter to exit...")
