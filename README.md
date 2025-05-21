# Advanced Multi-Core String Finder

## Description

This Python script is designed to efficiently search through a large number of files, including those in subdirectories and compressed `.gz` archives, for a predefined list of arbitrary text strings. It leverages multi-processing to significantly speed up the search process on multi-core CPUs and includes memory-efficient handling for very large plain text files.

The script outputs found strings with their context (file path, line number, and the full line), provides a real-time progress bar during processing, and also logs files that were skipped or couldn't be processed. Upon completion, it attempts to automatically open the generated output file (on Windows). This tool is ideal for tasks like log analysis, code auditing, data mining, or any scenario where you need to find occurrences of specific text patterns across a file system.

## Features

* **Generic String Searching:** Searches for any list of specified strings, not just URLs.
* **Recursive Directory Traversal:** Can search through the target directory and all its subdirectories.
* **Case-Insensitive Matching:** Searches are performed case-insensitively by default.
* **Literal String Searching:** Special characters in your search strings (e.g., '.', '*', '?') are treated as literals, not regex operators, ensuring exact matches for the provided strings.
* **`.gz` File Decompression:** Automatically decompresses and searches within `.gz` archives on the fly.
* **File Extension Ignore List:** Specify file extensions to be completely ignored by the script.
* **Parallel Processing:** Utilizes `concurrent.futures.ProcessPoolExecutor` to process multiple files in parallel, drastically reducing search time on multi-core systems.
* **Memory-Efficient Large File Handling:** For plain text files exceeding a defined size threshold, the script reads them line-by-line to prevent excessive memory consumption.
* **Progress Bar:** Displays a real-time progress bar using `tqdm`, showing the status of file processing.
* **Detailed Output:**
    * Logs each found string with a timestamp, full file path, line number, the string itself, and the context line.
    * Appends a list of files that were skipped (due to ignore rules or processing errors) to the output file.
* **Output File Management:** Clears the previous output file on each new run to prevent appending to old results. The script attempts to create the output directory if it doesn't exist.
* **Auto-Open Output File:** Attempts to automatically open the output file with the default system application upon script completion (primarily for Windows using `os.startfile`).
* **Cross-Platform (Python):** Built with standard Python libraries (plus `tqdm`), making it runnable on Windows, macOS, and Linux where Python 3 is installed.

## Prerequisites

* Python 3.6 or higher (due to f-strings, `concurrent.futures`, and general modern syntax).
* The `tqdm` library for the progress bar. You can install it via pip:
    ```bash
    pip install tqdm
    ```
* The script uses standard Python libraries (`os`, `re`, `datetime`, `gzip`, `traceback`, `concurrent.futures`), which are typically included with Python.

## Configuration

Before running the script, you need to configure several variables at the top of the Python file (e.g., `advanced_string_finder.py`):

1.  **`target_directory`**:
    * The root directory you want to search.
    * Example: `target_directory = r"C:\Logs\Production"` or `target_directory = "/var/log/app_logs"`

2.  **`output_file_path`**:
    * The full path where the output file (containing found strings and skipped file logs) will be saved.
    * Example: `output_file_path = r"C:\Search_Results\found_strings_output.txt"`

3.  **`include_subdirectories`**:
    * Set to `True` to search in subdirectories of `target_directory`.
    * Set to `False` to only search files directly within `target_directory`.
    * Example: `include_subdirectories = True`

4.  **`ignore_extensions`**:
    * A Python list of file extensions (lowercase, starting with a dot) to ignore. Files with these extensions will be skipped.
    * Example: `ignore_extensions = [".exe", ".dll", ".png", ".jpg", ".cur", ".zip"]`

5.  **`strings_to_search`**:
    * A Python list of the specific strings you want to find. The search is case-insensitive and literal.
    * Example:
        ```python
        strings_to_search = [
            "DATABASE_CONNECTION_ERROR",
            "Transaction ID: FAILED",
            "user_permissions_revoked",
            "critical_alert_code_#123"
        ]
        ```

6.  **`MASSIVE_PLAIN_TEXT_THRESHOLD_BYTES`**:
    * An integer representing a file size in bytes. Plain text files larger than this threshold will be read line-by-line to conserve memory. `.gz` files are always streamed.
    * Example (for 500 MB): `MASSIVE_PLAIN_TEXT_THRESHOLD_BYTES = 500 * 1024 * 1024`

## How to Run

1.  **Install `tqdm`:** If you haven't already, install the `tqdm` library:
    ```bash
    pip install tqdm
    ```
2.  **Save the script:** Save the Python code as a `.py` file (e.g., `finder_script.py`).
3.  **Configure:** Open the script and modify the configuration variables at the top as described above.
4.  **Open a terminal or command prompt (like PowerShell):**
    * Navigate to the directory where you saved the script: `cd path/to/script_directory`
    * Run the script using Python: `python finder_script.py` (or `py finder_script.py` on Windows).
5.  **Monitor Progress:** The script will print:
    * Initial configuration details.
    * The number of worker processes being used.
    * A progress bar showing files being processed.
    * Any errors encountered by worker processes (printed above the progress bar using `tqdm.write`).
    * A final summary of found strings and skipped files.
6.  **Output Review:**
    * Upon completion, the script will attempt to automatically open the output file (specified by `output_file_path`).
    * The console will display a summary and then pause, waiting for you to "Press Enter to exit...", allowing you to review console messages.

## Output File Structure

The output file will contain:

1.  **Found Strings:** Each line where a searched string is found will be logged in the format:
    ```
    [YYYY-MM-DD HH:MM:SS] File: /path/to/your/file.log | Line: 123 | Found String: "the_searched_string" | Context: The full line content where the string was found...
    ```
2.  **Skipped/Errored Files Log (if any):** Appended at the end of the file, under the header `--- Files Skipped or Errored During Processing ---`. Each entry will be in the format:
    ```
    File: /path/to/skipped/file.exe | Reason: Ignored extension: .exe
    File: /path/to/another/file.gz | Reason: Corrupted/Invalid .gz file: <error details from Python>
    ```

## Performance Notes

* **Multi-Core Utilization:** The script uses a `ProcessPoolExecutor` to distribute the processing of individual files across multiple CPU cores. The number of worker processes is dynamically set (typically `os.cpu_count() - 2`) to balance performance with system responsiveness.
* **Single Massive Files:**
    * For very large *plain text* files (exceeding `MASSIVE_PLAIN_TEXT_THRESHOLD_BYTES`), the script reads them line-by-line. This is memory-efficient and prevents out-of-memory errors but means the processing of that single file's content happens within one worker process (one core).
    * `.gz` files are always decompressed and read as a stream, which is also memory-efficient.
    * The primary speedup from parallelism comes when processing *multiple* files concurrently.
* **I/O Bottlenecks:** Disk speed can still be a limiting factor, especially if processing a vast number of files or very large files from slower storage.

## Limitations

* **Binary File Content:** The script is designed to search for text strings. While it attempts to read non-ignored, non-gz files as text (trying UTF-8 then Latin-1 with `errors='ignore'`), searching within compiled binaries or proprietary binary formats will likely not yield meaningful results.
* **Specific Structured Binary Formats:** Direct parsing of specific structured binary formats (e.g., raw systemd journal files if not plain text, `.evtx` event logs before conversion) is not supported. Such files should be converted to a text-based format (like CSV, plain text, or JSON lines) first if their internal content needs to be searched effectively by this script, or their extensions should be added to `ignore_extensions`.
