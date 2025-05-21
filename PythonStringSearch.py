import os
import re
import datetime
import gzip # For .gz file decompression
import traceback # For detailed error logging
import concurrent.futures # For parallel processing

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
    # ".zip", ".rar", # Other archive types you might want to ignore if not handling them
]

# List of specific strings to search for in the files.
# The script will search for these strings case-insensitively.
# Special characters in these strings will be treated as literal characters.
strings_to_search = [
    "edge-services-qa.stgedge.com", # This happens to be a URL
    "ERROR_CODE_XYZ",               # This could be an error code
    "UserLoginFailedEvent",         # This could be a specific event keyword
    "critical system alert",
    "testtest.com"
]

# Define a threshold for "massive" plain text files (in bytes).
# Files larger than this will be read line-by-line to conserve memory,
# instead of loading the entire file at once.
# Example: 500MB = 500 * 1024 * 1024
MASSIVE_PLAIN_TEXT_THRESHOLD_BYTES = 500 * 1024 * 1024

# --- Worker Function for Parallel Processing ---
def process_file_worker(file_path, compiled_patterns_with_originals):
    """
    Processes a single file: opens/decompresses, reads lines, and searches for specified strings.
    For massive plain text files, it reads line by line to save memory.

    Args:
        file_path (str): The path to the file to process.
        compiled_patterns_with_originals (list): A list of tuples, where each tuple is
                                                 (original_string, compiled_regex_pattern).
                                                 The pattern is used for searching.
                                                 The original_string is used for reporting.
    Returns:
        tuple: (file_path, list_of_found_result_strings, skip_reason_string_or_None)
               skip_reason is None if the file was processed (even if no strings were found),
               and contains an error message if the file could not be processed.
    """
    # This print indicates which file a worker is starting on.
    # In parallel execution, output from different workers might interleave.
    print(f"Worker starting on: {file_path}")

    found_results_for_this_file = []
    is_gz_file = file_path.lower().endswith(".gz")

    try:
        opened_file_stream = None # Will hold the file object for .gz or massive plain text

        # --- Handle .gz files (stream processing, memory efficient) ---
        if is_gz_file:
            try:
                opened_file_stream = gzip.open(file_path, 'rt', encoding='utf-8', errors='ignore')
            except gzip.BadGzipFile as e_bad_gz:
                return file_path, [], f"Corrupted/Invalid .gz file: {e_bad_gz}"
            except Exception as e_gz: # Other errors opening/reading gzip stream
                return file_path, [], f"Error reading gzipped file: {e_gz}"
        # --- Handle plain text files ---
        else:
            try:
                file_size = os.path.getsize(file_path)
                # For smaller plain text files, read all lines at once for potentially faster processing.
                if file_size <= MASSIVE_PLAIN_TEXT_THRESHOLD_BYTES:
                    lines_to_process_directly = []
                    try: # Try UTF-8 first
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f_text:
                            lines_to_process_directly = f_text.readlines()
                    except UnicodeDecodeError: # Fallback to Latin-1 if UTF-8 fails
                        print(f"Info (worker): UTF-8 decode failed for small file {file_path}, trying Latin-1.")
                        try:
                            with open(file_path, 'r', encoding='latin-1', errors='ignore') as f_text_latin:
                                lines_to_process_directly = f_text_latin.readlines()
                        except Exception as e_small_latin: # Error even with Latin-1
                            return file_path, [], f"Error opening/reading small text file with Latin-1: {e_small_latin}"
                    except Exception as e_small_utf8: # Other error with UTF-8
                        return file_path, [], f"Error opening/reading small text file with UTF-8: {e_small_utf8}"

                    # Process lines from the small file directly
                    for line_number, line_content in enumerate(lines_to_process_directly, 1):
                        for original_string, compiled_pattern in compiled_patterns_with_originals:
                            if compiled_pattern.search(line_content):
                                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                result = (f"[{timestamp}] File: {file_path} | Line: {line_number} | "
                                          f"Found String: \"{original_string}\" | Context: {line_content.strip()}")
                                found_results_for_this_file.append(result)
                    return file_path, found_results_for_this_file, None # Successfully processed small file

                else: # Massive plain text file, open a stream for line-by-line reading
                    print(f"Info (worker): File '{file_path}' is massive (>{MASSIVE_PLAIN_TEXT_THRESHOLD_BYTES / (1024*1024):.0f}MB), will read line-by-line.")
                    opened_file_stream = open(file_path, 'r', encoding='utf-8', errors='ignore')

            except Exception as e_open_prepare: # Error during size check or initial open attempt for plain text
                return file_path, [], f"Error preparing plain text file for reading: {e_open_prepare}"
        
        # --- Common stream processing logic (for opened .gz or massive plain text files) ---
        if opened_file_stream:
            try:
                for line_number, line_content in enumerate(opened_file_stream, 1):
                    for original_string, compiled_pattern in compiled_patterns_with_originals:
                        if compiled_pattern.search(line_content):
                            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            result = (
                                f"[{timestamp}] File: {file_path} | Line: {line_number} | "
                                f"Found String: \"{original_string}\" | Context: {line_content.strip()}"
                            )
                            found_results_for_this_file.append(result)
            except UnicodeDecodeError: # Fallback for massive plain text if primary utf-8 stream failed
                if not is_gz_file: # Only relevant for plain text massive files
                    try:
                        opened_file_stream.close() # Close previous utf-8 stream
                        print(f"Info (worker): Retrying massive plain text file '{file_path}' with Latin-1 encoding.")
                        with open(file_path, 'r', encoding='latin-1', errors='ignore') as f_latin_stream:
                            for line_number, line_content in enumerate(f_latin_stream, 1):
                                for original_string, compiled_pattern in compiled_patterns_with_originals:
                                    if compiled_pattern.search(line_content):
                                        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                        result = (f"[{timestamp}] File: {file_path} | Line: {line_number} | "
                                                  f"Found String: \"{original_string}\" | Context: {line_content.strip()}")
                                        found_results_for_this_file.append(result)
                    except Exception as e_latin_stream: # Error during Latin-1 stream attempt
                        return file_path, found_results_for_this_file, f"Error in latin-1 stream for massive plain text: {e_latin_stream}"
            except Exception as e_stream_read: # Other errors during stream reading
                 return file_path, found_results_for_this_file, f"Error reading stream for {file_path}: {e_stream_read}"
            finally:
                if opened_file_stream: # Ensure stream is closed
                    opened_file_stream.close()
        
        # Check if the file was processed but no strings were found (and it wasn't empty to begin with)
        if os.path.getsize(file_path) > 0 and not found_results_for_this_file:
            print(f"Info (worker): File '{file_path}' processed but no matching strings found or content was unsearchable/empty of relevant data.")

        return file_path, found_results_for_this_file, None # Success for this file

    except Exception as e_outer_worker: # Catch-all for any unexpected errors within the worker for this file
        return file_path, [], f"Unexpected error in worker for file '{file_path}': {e_outer_worker} \n{traceback.format_exc()}"

# --- Main Script Logic ---
def main_script_logic():
    # Validate that there are strings to search for
    if not strings_to_search:
        print("Error: The 'strings_to_search' list is empty. Please add strings to search for.")
        return

    # Pre-compile search strings into regex patterns for efficiency and case-insensitivity.
    # Stores tuples of (original_string, compiled_regex_pattern).
    compiled_patterns = []
    for s in strings_to_search:
        try:
            # re.escape ensures special characters in the search string are treated literally.
            # re.IGNORECASE makes the search case-insensitive.
            compiled_patterns.append((s, re.compile(re.escape(s), re.IGNORECASE)))
        except re.error as e:
            print(f"Error compiling regex for string '{s}': {e}. Skipping this string.")
    
    if not compiled_patterns: # If all string compilations failed
        print("Error: No valid strings to search for after attempting to compile patterns.")
        return

    initial_skipped_file_log = [] # Stores records of files skipped before parallel processing (e.g., ignored extension)

    # --- Print Initial Configuration and Search Parameters ---
    print(f"Searching for specific strings in: {target_directory}")
    if include_subdirectories: print("Including subdirectories.")
    else: print("Only searching top-level directory.")
    print(f"Output will be saved to: {output_file_path}")
    if ignore_extensions: print(f"Ignoring files with extensions: {', '.join(ignore_extensions)}")
    print("Strings being searched for (case-insensitive, literal match):")
    for s_original, _ in compiled_patterns: print(f"- {s_original}") # Print original strings
    print("---------------------------------------------------")

    # --- Prepare Output File (Clear if exists) ---
    if os.path.exists(output_file_path):
        try:
            os.remove(output_file_path)
            print(f"Cleared existing output file: {output_file_path}")
        except OSError as e:
            print(f"Warning: Could not clear existing output file '{output_file_path}': {e}")
    
    # Ensure output directory exists before workers try to write (though workers don't write directly to final file)
    # This is more for the final aggregation and skipped log.
    try:
        output_dir_main = os.path.dirname(output_file_path)
        if output_dir_main and not os.path.exists(output_dir_main):
            os.makedirs(output_dir_main)
            print(f"Created output directory: {output_dir_main}")
    except Exception as e_dir_create:
        print(f"CRITICAL ERROR: Could not create output directory '{os.path.dirname(output_file_path)}': {e_dir_create}. Exiting.")
        return

    # --- Discover Files to Consider ---
    files_to_consider = [] # All files found before ignoring extensions
    try:
        if include_subdirectories:
            for root, _, files in os.walk(target_directory):
                for file_name in files:
                    # os.walk can list directories as files in some rare edge cases with symlinks,
                    # so an explicit check can be useful, though usually 'files' from os.walk are files.
                    if not os.path.isdir(os.path.join(root, file_name)):
                        files_to_consider.append(os.path.join(root, file_name))
        else: # Only top-level directory
            for file_name in os.listdir(target_directory):
                full_path = os.path.join(target_directory, file_name)
                if os.path.isfile(full_path): # Ensure it's a file
                    files_to_consider.append(full_path)
    except FileNotFoundError:
        err_msg = f"Target directory '{target_directory}' not found."
        print(f"CRITICAL ERROR: {err_msg}")
        initial_skipped_file_log.append({'path': target_directory, 'reason': err_msg})
    except Exception as e: # Other errors accessing directory (e.g., permissions)
        err_msg = f"Error accessing target directory '{target_directory}': {e}"
        print(f"CRITICAL ERROR: {err_msg}")
        initial_skipped_file_log.append({'path': target_directory, 'reason': err_msg})

    # Handle cases where directory access failed or no files were found
    if not files_to_consider:
        if not initial_skipped_file_log: # No specific error logged, just no files
             print(f"No files found in '{target_directory}'.")
        # Log any initial skipped items (like directory access failure) and exit
        if initial_skipped_file_log: log_skipped_files(initial_skipped_file_log, output_file_path)
        return

    print(f"Found {len(files_to_consider)} total file items. Filtering based on ignore_extensions...")

    # --- Filter out ignored files and prepare arguments for workers ---
    files_to_process_with_args = []
    for file_path in files_to_consider:
        # Get file extension, convert to lowercase for case-insensitive comparison
        file_ext = os.path.splitext(file_path)[1].lower()
        if file_ext in ignore_extensions:
            reason = f"Ignored extension: {file_ext}"
            initial_skipped_file_log.append({'path': file_path, 'reason': reason})
            continue # Skip this file
        # Prepare arguments for the worker function: (file_path, list_of_compiled_patterns)
        files_to_process_with_args.append((file_path, compiled_patterns))

    if not files_to_process_with_args: # All files were ignored or none were found initially
        print(f"No files to process after applying ignore list.")
        if initial_skipped_file_log: log_skipped_files(initial_skipped_file_log, output_file_path)
        return

    print(f"Submitting {len(files_to_process_with_args)} files to worker processes...")

    # --- Parallel Processing ---
    all_found_result_lines = [] # Stores all result strings from all workers
    worker_skipped_file_log = [] # Stores records of files skipped by workers due to errors
    found_files_set = set() # Tracks unique file paths where strings were found

    # Determine number of worker processes.
    # Using os.cpu_count() - 2 can be a good starting point to leave resources for OS/other tasks.
    # Ensure at least 1 worker.
    num_workers = max(1, os.cpu_count() - 2 if os.cpu_count() and os.cpu_count() > 2 else 1)
    print(f"Using up to {num_workers} worker processes.")

    processed_count = 0
    total_files_to_process = len(files_to_process_with_args)

    # Using ProcessPoolExecutor to manage a pool of worker processes
    with concurrent.futures.ProcessPoolExecutor(max_workers=num_workers) as executor:
        # Submit all file processing tasks to the executor pool
        # future_to_filepath maps a Future object to the filepath it's processing, for easier error reporting
        future_to_filepath = {
            executor.submit(process_file_worker, *args_for_worker): args_for_worker[0] 
            for args_for_worker in files_to_process_with_args
        }

        # Process results as they are completed by the workers
        for future in concurrent.futures.as_completed(future_to_filepath):
            file_path_processed = future_to_filepath[future]
            processed_count += 1
            
            # Basic progress indicator
            if total_files_to_process > 20: # Avoid too much printing for few files
                # Print a dot for most, and a count at intervals
                progress_marker = "." if processed_count % (total_files_to_process // 20 if total_files_to_process > 100 else 10) != 0 else f" {processed_count}/{total_files_to_process} "
                print(progress_marker, end="", flush=True)
            else: # For fewer files, print each completion
                 print(f"\nCompleted: {os.path.basename(file_path_processed)} ({processed_count}/{total_files_to_process})")

            try:
                # Get the result from the worker: (file_path, list_of_results, skip_reason)
                _fp_returned, result_lines_from_worker, skip_reason = future.result()
                if skip_reason: # Worker reported an error for this file
                    worker_skipped_file_log.append({'path': file_path_processed, 'reason': skip_reason})
                if result_lines_from_worker: # Worker found matching strings
                    all_found_result_lines.extend(result_lines_from_worker)
                    found_files_set.add(file_path_processed) # Mark this file as having matches
            except Exception as exc: # Error retrieving result from future (e.g., worker process crashed)
                reason = f"Worker process CRASHED or unhandled error for {file_path_processed}: {exc} \n{traceback.format_exc()}"
                print(f"\nERROR: {reason}") # Ensure newline if progress dots were used
                worker_skipped_file_log.append({'path': file_path_processed, 'reason': reason})
    
    print("\nAll worker processes finished.") # Newline after any progress printing

    # Consolidate all skipped file logs (initial skips + worker skips)
    final_skipped_log = initial_skipped_file_log + worker_skipped_file_log

    # --- Write Aggregated Results to Output File ---
    if all_found_result_lines:
        print(f"\nAggregating and writing {len(all_found_result_lines)} found lines to output file...")
        try:
            # Append results to the (cleared) output file
            with open(output_file_path, 'a', encoding='utf-8') as out_f:
                for line in all_found_result_lines:
                    out_f.write(line + "\n")
            print("Finished writing results.")
        except IOError as e_write:
            print(f"CRITICAL ERROR: Could not write results to '{output_file_path}': {e_write}")

    # --- Final Summary ---
    print("---------------------------------------------------")
    print("Search complete!")
    if all_found_result_lines:
        print(f"Results saved to: {output_file_path}")
        print(f"Total matching lines found: {len(all_found_result_lines)} in {len(found_files_set)} file(s).")
    else:
        print("No occurrences of the specified strings were found in the searched files.")
    
    # Log any skipped or errored files
    if final_skipped_log:
        log_skipped_files(final_skipped_log, output_file_path)

def log_skipped_files(skipped_records, output_file_path_param):
    """
    Helper function to print and append skipped file records to the output file.
    """
    if not skipped_records:
        return
    
    skipped_header = "\n--- Files Skipped or Errored During Processing ---"
    print(skipped_header)
    try:
        # Ensure output directory exists for the skipped log part too
        output_dir = os.path.dirname(output_file_path_param)
        if output_dir and not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
                # print(f"Info: Created output directory for skipped log: {output_dir}") # Can be noisy
            except Exception:
                pass # If it fails here, the write below will likely also fail.

        with open(output_file_path_param, 'a', encoding='utf-8') as out_f:
            out_f.write(skipped_header + "\n")
            for record in skipped_records:
                log_entry = f"File: {record['path']} | Reason: {record['reason']}"
                print(log_entry) # Also print to console
                out_f.write(log_entry + "\n")
    except IOError as e:
        print(f"Error: Could not write skipped files log to '{output_file_path_param}': {e}")

# This guard is crucial for multiprocessing to work correctly on some platforms (like Windows).
# It ensures that main_script_logic() is only called when the script is executed directly,
# not when it's imported by worker processes.
if __name__ == "__main__":
    script_start_time = datetime.datetime.now()
    print(f"Script started at: {script_start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        main_script_logic()
    except Exception as e: # Catch any unexpected critical errors in the main execution flow
        print("---------------------------------------------------")
        print("AN UNEXPECTED CRITICAL ERROR OCCURRED IN THE SCRIPT (MAIN BLOCK):")
        print(str(e))
        print("---------------------------------------------------")
        traceback.print_exc()
    finally:
        script_end_time = datetime.datetime.now()
        print(f"Script finished at: {script_end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Total execution time: {script_end_time - script_start_time}")
        print("\n--- Script execution finished or was interrupted ---")
        input("Press Enter to exit...")