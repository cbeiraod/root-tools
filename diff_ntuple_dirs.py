#############################################################################
# zlib License
#
# (C) 2025 Cristóvão Beirão da Cruz e Silva <cbeiraod@cern.ch>
#
# This software is provided 'as-is', without any express or implied
# warranty.  In no event will the authors be held liable for any damages
# arising from the use of this software.
#
# Permission is granted to anyone to use this software for any purpose,
# including commercial applications, and to alter it and redistribute it
# freely, subject to the following restrictions:
#
# 1. The origin of this software must not be misrepresented; you must not
#    claim that you wrote the original software. If you use this software
#    in a product, an acknowledgment in the product documentation would be
#    appreciated but is not required.
# 2. Altered source versions must be plainly marked as such, and must not be
#    misrepresented as being the original software.
# 3. This notice may not be removed or altered from any source distribution.
#############################################################################

from pathlib import Path
import logging
import ROOT
import hashlib
from natsort import natsorted

def fill_compare_file_dict(
        file_dict: dict,
        path: Path,
        compare_key: str,
        ignore_suffix: str = "",
                           ):
    for file in path.iterdir():
        # Only consider root files
        if not file.is_file():
            continue
        if not file.suffix == ".root":
            continue

        dict_key = file.name

        if ignore_suffix is not None and ignore_suffix != "":
            parts = dict_key.split(".")
            if parts[0][-len(ignore_suffix):] == ignore_suffix:
                dict_key = parts[0][:-len(ignore_suffix)] + "." + parts[1]

        if dict_key not in file_dict:
            file_dict[dict_key] = {}
        file_dict[dict_key][compare_key] = file

def compare_exists(
        file_dict: dict,
        left_key: str = "left",
        right_key: str = "right",
                   ):
    for dict_key in file_dict:
        # Check if file exists on left
        exist_left = False
        if left_key in file_dict[dict_key] and file_dict[dict_key][left_key] is not None:
            if file_dict[dict_key][left_key].exists():
                exist_left = True

        # Check if file exists on right
        exist_right = False
        if right_key in file_dict[dict_key] and file_dict[dict_key][right_key] is not None:
            if file_dict[dict_key][right_key].exists():
                exist_right = True

        # Do the checks
        file_dict[dict_key]["both_exist"] = False
        if exist_left and not exist_right:
            file_dict[dict_key]["message"] = "This file does not exist on the right"
        elif exist_right and not exist_left:
            file_dict[dict_key]["message"] = "This file does not exist on the left"
        elif not exist_right and not exist_left:
            file_dict[dict_key]["message"] = "This file does not exist anywhere... why are we here?"
        else:
            file_dict[dict_key]["both_exist"] = True

def compare_root(
        file_dict: dict,
        left_key: str = "left",
        right_key: str = "right",
        tree_name: str = "bdttree",
        variable_name: str = "nVert",
        variable_min: float = 0.0,
        variable_max: float = 100.0,
        logger: logging.Logger | None = None,
                 ):
    if logger is None:
        logger = logging.getLogger('compare_root_files')

    for file_name in file_dict:
        if "message" in file_dict[file_name]:
            continue

        logger.debug(f"Checking file {file_name}")

        left_file = file_dict[file_name][left_key]
        right_file = file_dict[file_name][right_key]

        left_root_file = ROOT.TFile(str(left_file), "READ")
        right_root_file = ROOT.TFile(str(right_file), "READ")

        logger.debug(f"Checking if root files are good")
        left_good = not left_root_file.IsZombie()
        right_good = not right_root_file.IsZombie()

        if   not left_good and not right_good:
            file_dict[file_name]["message"] = "Unable to open any of the two root files."
            continue
        elif     left_good and not right_good:
            file_dict[file_name]["message"] = f"Unable to open the {right_key} root file."
            continue
        elif not left_good and     right_good:
            file_dict[file_name]["message"] = f"Unable to open the {left_key} root file."
            continue


        logger.debug(f"Looking for tree with name {tree_name}")
        tree_exist_left = left_root_file.GetListOfKeys().Contains(tree_name)
        tree_exist_right = right_root_file.GetListOfKeys().Contains(tree_name)

        if   not tree_exist_left and not tree_exist_right:
            file_dict[file_name]["message"] = f"Unable to find the {tree_name} tree for any of the files."
            continue
        elif     tree_exist_left and not tree_exist_right:
            file_dict[file_name]["message"] = f"Unable to find the {tree_name} tree for the {right_key} file."
            continue
        elif not tree_exist_left and     tree_exist_right:
            file_dict[file_name]["message"] = f"Unable to find the {tree_name} tree for the {left_key} file."
            continue


        logger.debug("Comparing tree branches")
        left_tree = left_root_file.Get(tree_name)
        right_tree = right_root_file.Get(tree_name)

        left_branches = left_tree.GetNbranches()
        right_branches = right_tree.GetNbranches()

        if left_branches > right_branches:
            file_dict[file_name]["additional message"] = f"More branches found on the {left_key} file, maybe {right_key} file is a skim? ({left_branches} vs {right_branches})"
        elif left_branches < right_branches:
            file_dict[file_name]["additional message"] = f"More branches found on the {right_key} file, maybe {left_key} file is a skim? ({right_branches} vs {left_branches})"


        logger.debug("Comparing tree lengths")
        left_events = left_tree.GetEntries()
        right_events = right_tree.GetEntries()

        if left_events > right_events:
            file_dict[file_name]["message"] = f"More events found on the {left_key} file, maybe {right_key} file is filtered? ({left_events} vs {right_events})"
            continue
        elif left_events < right_events:
            file_dict[file_name]["message"] = f"More events found on the {right_key} file, maybe {left_key} file is filtered? ({right_events} vs {left_events})"
            continue
        elif left_events == 0:
            file_dict[file_name]["message"] = f"There are no events in any file."
            continue


        logger.debug(f"Looking for variable with name {variable_name}")
        variable_exist_left = left_tree.GetListOfBranches().Contains(variable_name)
        variable_exist_right = right_tree.GetListOfBranches().Contains(variable_name)

        if   not variable_exist_left and not variable_exist_right:
            file_dict[file_name]["message"] = f"Unable to find the {variable_name} variable for any of the files. Maybe it was skimmed out?"
            continue
        elif     variable_exist_left and not variable_exist_right:
            file_dict[file_name]["message"] = f"Unable to find the {variable_name} variable for the {right_key} file. Maybe it was skimmed out?"
            continue
        elif not variable_exist_left and     variable_exist_right:
            file_dict[file_name]["message"] = f"Unable to find the {variable_name} variable for the {left_key} file. Maybe it was skimmed out?"
            continue


        logger.debug(f"Comparing the mean of the variable {variable_name}")
        #left_branch = left_tree.GetBranch(variable_name)
        #right_branch = right_tree.GetBranch(variable_name)

        #left_vals = []
        #for event in range(left_events):
        #    left_tree.GetEvent(event)
        #    left_vals += [getattr(left_tree,variable_name)]

        #right_vals = []
        #for event in range(right_events):
        #    right_tree.GetEvent(event)
        #    right_vals += [getattr(right_tree,variable_name)]

        #left_mean = sum(left_vals) / len(left_vals)
        #right_mean = sum(right_vals) / len(right_vals)

        left_hist = ROOT.TH1D("left_hist", "left_hist", 100, variable_min, variable_max)
        left_tree.Draw(f"{variable_name}>>left_hist", "", "goff")

        right_hist = ROOT.TH1D("right_hist", "right_hist", 100, variable_min, variable_max)
        right_tree.Draw(f"{variable_name}>>right_hist", "", "goff")

        left_mean = left_hist.GetMean()
        right_mean = right_hist.GetMean()

        if left_mean != right_mean:
            file_dict[file_name]["message"] = f"The mean of the {variable_name} variable does not match between the two files, they are different. {left_key}: {left_mean}; {right_key}: {right_mean}"
            if "additional message" in file_dict[file_name]:
                file_dict[file_name].pop("additional message", None)
            continue

        if "additional message" in file_dict[file_name]:
            file_dict[file_name]["message"] = file_dict[file_name].pop("additional message", "")

        left_root_file.Close()
        right_root_file.Close()

def compare_files(
        file_dict: dict,
        left_key: str = "left",
        right_key: str = "right",
        logger: logging.Logger | None = None,
                 ):
    if logger is None:
        logger = logging.getLogger('compare_root_files')

    for file_name in file_dict:
        if "message" in file_dict[file_name]:
            continue

        logger.debug(f"Checking file {file_name}")

        left_file: Path = file_dict[file_name][left_key]
        right_file: Path = file_dict[file_name][right_key]

        logger.debug(f"Comparing file sizes")
        left_size = left_file.stat().st_size
        right_size = right_file.stat().st_size

        if left_size != right_size:
            file_dict[file_name]["message"] = f"The file size does not match between the two files, they are different. {left_key}: {left_size}; {right_key}: {right_size}"
            continue

        logger.debug(f"Comparing file hashes")
        with left_file.open("rb") as binary_file:
            digest = hashlib.file_digest(binary_file, "md5")
            left_hash = digest.hexdigest()
        with right_file.open("rb") as binary_file:
            digest = hashlib.file_digest(binary_file, "md5")
            right_hash = digest.hexdigest()

        if left_hash != right_hash:
            file_dict[file_name]["message"] = f"The file hashes do not match between the two files, they are different."
            continue

def script_main(
                left_path: Path,
                right_path: Path,
                output_path: Path | None,
                tree_name: str = "bdttree",
                variable_name: str = "nVert",
                variable_min: float = 0.0,
                variable_max: float = 100.0,
                show_matches: bool = False,
                ignore_left_suffix: str = "",
                ignore_right_suffix: str = "",
                ):
    logger = logging.getLogger('diff_ntuple_dirs')

    compare_dict = {}

    logger.info(f'Loading all the file names from {str(left_path)}')
    fill_compare_file_dict(compare_dict, left_path, "left", ignore_suffix=ignore_left_suffix)
    logger.info(f'Loading all the file names from {str(right_path)}')
    fill_compare_file_dict(compare_dict, right_path, "right", ignore_suffix=ignore_right_suffix)

    logger.info(f'Checking if files exist on both sides')
    compare_exists(compare_dict, left_key="left", right_key="right")

    logger.info(f'Checking ROOT file characteristics match on both sides')
    compare_root(compare_dict, left_key="left", right_key="right", tree_name=tree_name, variable_name=variable_name, variable_min=variable_min, variable_max=variable_max)

    logger.info(f'Checking file characteristics match on both sides')
    compare_files(compare_dict, left_key="left", right_key="right")

    #print_count = 0
    debug_print = False
    #debug_print = True

    if not debug_print:
        if output_path is not None:
            outfile = output_path.open("w")

    for key in natsorted(compare_dict.keys()):
        if "message" in compare_dict[key]:
            message = compare_dict[key]["message"]
            if "additional message" in compare_dict[key]:
                message += "; " + compare_dict[key]["additional message"]
        else:
            message = ""

        if not debug_print:
            if message == "":
                if show_matches:
                    if output_path is not None:
                        outfile.write(f"{key}: Matches on both sides\n")
                    else:
                        print(f"{key}: Matches on both sides")
                continue
            if output_path is not None:
                outfile.write(f"{key}: {message}\n")
            else:
                print(f"{key}: {message}")
        else:
            print(compare_dict[key])

        #print_count += 1
        #if print_count > 10:
        #    break

def main():
    import argparse

    parser = argparse.ArgumentParser(
                    prog='diff_ntuple_dirs.py',
                    description='This script compares two directories containing flat ntuples, the script first checks for files with the same names and if found, it then looks for a tree, if found, it compares the tree length, if matching the mean of a variable is compared and if matching the length and CRC of the files are compared',
                    #epilog='Text at the bottom of help'
                    )

    parser.add_argument(
        '-l',
        '--leftPath',
        metavar = 'PATH',
        type = Path,
        help = 'Path to the directory to be placed on the left',
        required = True,
        #default = "./data",
        dest = 'left_path',
    )
    parser.add_argument(
        '-r',
        '--rightPath',
        metavar = 'PATH',
        type = Path,
        help = 'Path to the directory to be placed on the right',
        required = True,
        #default = "./data",
        dest = 'right_path',
    )
    parser.add_argument(
        '-o',
        '--outputFile',
        metavar = 'PATH',
        type = Path,
        help = 'Path to the file to store the output. If not specified, output will be printed to terminal',
        required = False,
        dest = 'output_path',
    )
    parser.add_argument(
        '-t',
        '--treeName',
        metavar = 'STR',
        type = str,
        help = 'Name of the tree contained in the root files. Default: bdttree',
        default = 'bdttree',
        dest = 'tree_name',
    )
    parser.add_argument(
        '-v',
        '--variableName',
        metavar = 'STR',
        type = str,
        help = 'Name of the variable to check in the tree. Default: nVert',
        default = 'nVert',
        dest = 'variable_name',
    )
    parser.add_argument(
        '--variableMin',
        metavar = 'MIN',
        type = float,
        help = 'Minimum value of the variable for the internal ROOT histogram limits in order to obtain the mean. Default: 0',
        default = 0.0,
        dest = 'variable_min',
    )
    parser.add_argument(
        '--variableMax',
        metavar = 'MAX',
        type = float,
        help = 'Maximum value of the variable for the internal ROOT histogram limits in order to obtain the mean. Default: 100',
        default = 100.0,
        dest = 'variable_max',
    )
    parser.add_argument(
        '-m',
        '--showMatches',
        help = 'If set, print out the files that match in addition to the differences',
        action = 'store_true',
        dest = 'show_matches',
    )
    parser.add_argument(
        '--ignoreLeftSuffix',
        metavar = 'STR',
        type = str,
        help = 'Suffix to ignore on the files on the left',
        dest = 'ignore_left_suffix',
    )
    parser.add_argument(
        '--ignoreRightSuffix',
        metavar = 'STR',
        type = str,
        help = 'Suffix to ignore on the files on the right',
        dest = 'ignore_right_suffix',
    )
    parser.add_argument(
        '--log-level',
        help = 'Set the logging level. Default: WARNING',
        choices = ["CRITICAL","ERROR","WARNING","INFO","DEBUG","NOTSET"],
        default = "WARNING",
        dest = 'log_level',
    )
    parser.add_argument(
        '--log-file',
        help = 'If set, the full log will be saved to a file (i.e. the log level is ignored)',
        action = 'store_true',
        dest = 'log_file',
    )

    args = parser.parse_args()

    if args.log_file:
        logging.basicConfig(filename='logging.log', filemode='w', encoding='utf-8', level=logging.NOTSET)
    else:
        if args.log_level == "CRITICAL":
            logging.basicConfig(level=50)
        elif args.log_level == "ERROR":
            logging.basicConfig(level=40)
        elif args.log_level == "WARNING":
            logging.basicConfig(level=30)
        elif args.log_level == "INFO":
            logging.basicConfig(level=20)
        elif args.log_level == "DEBUG":
            logging.basicConfig(level=10)
        elif args.log_level == "NOTSET":
            logging.basicConfig(level=0)

    left_path: Path = args.left_path
    if not left_path.exists():
        raise RuntimeError("The left path does not exist")
    left_path = left_path.absolute()

    right_path: Path = args.right_path
    if not right_path.exists():
        raise RuntimeError("The right path does not exist")
    right_path = right_path.absolute()

    output_path: Path = args.output_path
    if output_path is not None:
        if output_path.exists():
            logging.error("You must define a valid data output file, i.e. a file which does not yet exist")
            exit(1)
        output_path = output_path.absolute()

    script_main(
        left_path,
        right_path,
        output_path,
        args.tree_name,
        args.variable_name,
        args.variable_min,
        args.variable_max,
        args.show_matches,
        args.ignore_left_suffix,
        args.ignore_right_suffix,
                )

if __name__ == "__main__":
    main()