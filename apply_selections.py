#############################################################################
# zlib License
#
# (C) 2023 Cristóvão Beirão da Cruz e Silva <cbeiraod@cern.ch>
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

def script_main(
                input_path: Path,
                output_path: Path,
                json_file: Path,
                tree_name: str = "bdttree",
                ):
    logger = logging.getLogger('apply_selections')

    import json

    prefilter = None
    selections = {}
    with open(json_file) as file:
        selection_data = json.load(file)

        if "prefilter" in selection_data:
            prefilter = selection_data["prefilter"]

        if "cuts" in selection_data:
            for entry in selection_data["cuts"]:
                selections[entry['name']] = entry['expression']

        del selection_data

    filter_path = None
    if prefilter is not None:
        filter_path = output_path / "Prefilter"
        filter_path.mkdir(exist_ok = True)

    for file in input_path.iterdir():
        if not file.is_file():
            continue
        if not file.suffix == ".root":
            continue

        # Skip not data files
        if file.name == "puWeights.root":
            continue

        logger.info(f'Processing file {file.name}')

        infile = ROOT.TFile(str(file), "READ")
        intree = infile.Get(tree_name)
        orig_events = intree.GetEntries()
        logger.debug(f'Started with {orig_events} in the original tree')

        if prefilter is not None:
            logger.debug(f'Applying the prefilter')
            filter_file = ROOT.TFile(str(filter_path / file.name), "RECREATE")
            filter_tree = intree.CopyTree(prefilter)
            filtered_events = filter_tree.GetEntries()
            logger.debug(f'Filtered down to {filtered_events} events with the prefilter')

            filter_tree.Write()
            intree = filter_tree

        for selection in selections:
            selection_path = output_path / selection
            selection_path.mkdir(exist_ok = True)

            selection_file = ROOT.TFile(str(selection_path / file.name), "RECREATE")
            selection_tree = intree.CopyTree(selections[selection])
            selected_events = selection_tree.GetEntries()
            logger.debug(f'Got {selected_events} events for selection {selection}')

            selection_tree.Write()
            selection_file.Close()

        if prefilter is not None:
            filter_file.Close()
        infile.Close()

def main():
    import argparse

    parser = argparse.ArgumentParser(
                    prog='apply_selections.py',
                    description='This script applies one or more different selections to a set of input root files, with an optional common prefilter',
                    #epilog='Text at the bottom of help'
                    )

    parser.add_argument(
        '-i',
        '--inputPath',
        metavar = 'PATH',
        type = Path,
        help = 'Path to the directory containing all the input root files.',
        required = True,
        #default = "./data",
        dest = 'input_path',
    )
    parser.add_argument(
        '-o',
        '--outputPath',
        metavar = 'PATH',
        type = Path,
        help = 'Path to the output directory. A subdirectory will be created for each selection specified in the json file as well as the prefilter if any is defined.',
        required = True,
        dest = 'output_path',
    )
    parser.add_argument(
        '-j',
        '--jsonFile',
        metavar = 'FILE',
        type = Path,
        help = 'Path to the json file describing the prefilter and selections.',
        required = True,
        dest = 'json_file',
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
        '-l',
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

    input_path: Path = args.input_path
    if not input_path.exists():
        raise RuntimeError("The input path does not exist")
    input_path = input_path.absolute()

    output_path: Path = args.output_path
    if not output_path.exists() or not output_path.is_dir():
        logging.error("You must define a valid data output path")
        exit(1)
    output_path = output_path.absolute()

    json_file: Path = args.json_file
    if not json_file.exists() or not json_file.is_file():
        logging.error("You must define an existing json file describing the prefilter and selections")
        exit(1)
    json_file = json_file.absolute()

    script_main(input_path, output_path, json_file, args.tree_name)

if __name__ == "__main__":
    main()