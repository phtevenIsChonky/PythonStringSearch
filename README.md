# Advanced Multi-Core String Finder

## Description

This Python script is designed to efficiently search through a large number of files, including those in subdirectories and compressed `.gz` archives, for a predefined list of strings. It leverages multi-processing to significantly speed up the search process on multi-core CPUs and includes memory-efficient handling for very large plain text files. The script outputs found strings with their context (file path, line number, and the full line) and also logs files that were skipped or couldn't be processed.

This script is ideal for tasks like log analysis, code auditing, or any scenario where you need to find occurrences of specific text patterns across a file system.

## Features

* **Recursive Directory Traversal:** Can search through the target directory and all its subdirectories.
* **Configurable Search Strings:** Easily define a list of strings to search for.
* **Case-Insensitive Matching:** Searches are performed case-insensitively.
* **Literal String Searching:** Special characters in your search strings are treated as literals, not regex operators (due to `re.escape()`).
* **`.gz` File Decompression:** Automatically decompresses and searches within `.gz` archives.
* **File Extension Ignore List:** Specify file extensions to be completely ignored by the script.
* **Parallel Processing:** Utilizes `concurrent.futures.ProcessPoolExecutor` to process multiple files in parallel, drastically reducing search time on multi-core systems.
* **Memory-Efficient Large File Handling:** For plain text files exceeding a defined size threshold, the script reads them line-by-line to prevent excessive memory consumption.
* **Detailed Output:**
    * Logs each found string with a timestamp, full file path, line number, the string itself, and the context line.
    * Appends a list of files that were skipped (due to ignore rules or processing errors) to the output file.
* **Output File Management:** Clears the previous output file on each new run to prevent appending to old results.
* **Cross-Platform (Python):** Built with standard Python libraries, making it runnable on Windows, macOS, and Linux where Python 3 is installed.

## Prerequisites

* Python 3.6 or higher (due to f-strings and `concurrent.futures` usage).
* The script uses only standard Python libraries (`os`, `re`, `datetime`, `gzip`, `traceback`, `concurrent.futures`), so no external packages need to be installed via pip.

## Configuration

Before running the script, you need to configure several variables at the top of the Python file (`your_script_name.py`):

1.  **`target_directory`**:
    * The root directory you want to search.
    * Example: `target_directory = r"C:\Logs"` or `target_directory = "/var/log"`

2.  **`output_file_path`**:
    * The full path where the output file (containing found strings and skipped file logs) will be saved. The script will create the output directory if it doesn't exist.
    * Example: `output_file_path = r"C:\Search_Results\found_strings.txt"`

3.  **`include_subdirectories`**:
    * Set to `True` to search in subdirectories of `target_directory`.
    * Set to `False` to only search files directly within `target_directory`.
    * Example: `include_subdirectories = True`

4.  **`ignore_extensions`**:
    * A Python list of file extensions (lowercase, starting with a dot) to ignore. Files with these extensions will be skipped.
    * Example: `ignore_extensions = [".exe", ".dll", ".png", ".jpg", ".cur"]`

5.  **`strings_to_search`**:
    * A Python list of strings you want to find. The search is case-insensitive and literal.
    * Example:
        ```python
        strings_to_search = [
            "ERROR_CONNECTION_FAILED",
            "access denied for user",
            "confidential_project_alpha",
            "[example.com/specific_path](https://example.com/specific_path)"
        ]
        ```

6.  **`MASSIVE_PLAIN_TEXT_THRESHOLD_BYTES`**:
    * An integer representing a file size in bytes. Plain text files larger than this threshold will be read line-by-line to conserve memory, rather than loading the entire file at once. `.gz` files are always streamed.
    * Example (500 MB): `MASSIVE_PLAIN_TEXT_THRESHOLD_BYTES = 500 * 1024 * 1024`

## How to Run

1.  **Save the script:** Save the Python code as a `.py` file (e.g., `advanced_string_finder.py`).
2.  **Configure:** Open the script and modify the configuration variables at the top as described above.
3.  **Open a terminal or command prompt:**
    * Navigate to the directory where you saved the script: `cd path/to/script_directory`
    * Run the script using Python: `python advanced_string_finder.py` (or `py advanced_string_finder.py` on Windows if `py` is your launcher).
4.  **Monitor Progress:** The script will print information to the console, including:
    * Initial configuration.
    * A message when each worker process starts on a file.
    * A progress indicator showing the number of files completed.
    * A final summary of found strings and skipped files.
5.  **Check Output:** Once completed, the results will be in the file specified by `output_file_path`. The script will also pause and wait for you to "Press Enter to exit..." so you can review the console summary.

## Output File Structure

The output file specified by `output_file_path` will contain:

1.  **Found Strings:** Each line where a searched string is found will be logged in the format:
    ```
    [YYYY-MM-DD HH:MM:SS] File: /path/to/your/file.log | Line: 123 | Found String: "searched_string_here" | Context: The full line content where the string was found...
    ```
2.  **Skipped/Errored Files Log (if any):** Appended at the end of the file, under the header `--- Files Skipped or Errored During Processing ---`. Each entry will be in the format:
    ```
    File: /path/to/skipped/file.exe | Reason: Ignored extension: .exe
    File: /path/to/another/file.gz | Reason: Corrupted/Invalid .gz file: <error details>
    ```

## Performance Notes

* **Multi-Core Utilization:** The script uses a `ProcessPoolExecutor` to distribute the processing of individual files across multiple CPU cores. The number of worker processes is typically set to `os.cpu_count() - 2` to balance load and system responsiveness. This significantly speeds up searches across many files.
* **Single Massive Files:**
    * For very large *plain text* files (exceeding `MASSIVE_PLAIN_TEXT_THRESHOLD_BYTES`), the script reads them line-by-line to be memory-efficient. This prevents out-of-memory errors but the processing of that single file's content still happens within one worker process (one core).
    * `.gz` files are always decompressed and read as a stream, which is memory-efficient.
    * The primary speedup from parallelism comes when processing *multiple* files. A single file, even if massive, will primarily be processed by one core at a time.
* **I/O Bound Tasks:** If your system has slow disk I/O, this might become a bottleneck even with parallel processing.

## Limitations

* **Binary File Content:** The script is designed to search for text strings. While it can *attempt* to read any non-ignored, non-gz file as text (trying UTF-8 then Latin-1), searching for strings within compiled binaries or proprietary binary formats will likely not yield meaningful results. The `errors='ignore'` flag means unreadable binary content will be skipped over silently within a line.
* **Specific Binary Formats:** Direct parsing of specific structured binary formats (e.g., raw systemd journal files, `.evtx` before conversion) is not supported. Such files should be converted to a text-based format (like CSV, plain text, or JSON lines) first if their content needs to be searched by this script, or added to `ignore_extensions`.
* **No Intra-File Parallelism for CPU-Bound Search:** The search for strings within the lines of a single file (after it's read/decompressed) is performed sequentially by the worker assigned to that file. For extremely long lines or highly complex (though currently not used) regex patterns, this part could be CPU-intensive for that single worker.
