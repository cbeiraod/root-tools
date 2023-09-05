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
import random
from array import array

def script_main(
                input_path: Path,
                output_path: Path,
                tree_name: str = "bdttree",
                train_factor: int = 1,
                test_factor: int = 1,
                seed: int = None,
                ):
    logger = logging.getLogger('split_train_test')

    if seed is not None:
        random.seed(seed)

    train_path = output_path / "Train"
    train_path.mkdir(exist_ok = True)

    test_path = output_path / "Test"
    test_path.mkdir(exist_ok = True)

    train_probability = float(train_factor) / float(train_factor + test_factor)  # Events are either train or test, there is no other category possible

    for file in input_path.iterdir():
        if not file.is_file():
            continue
        if not file.suffix == ".root":
            continue

        # Skip not data files
        if file.name == "puWeights.root":
            continue

        # Skip data samples
        if file.name[:4] == "Data":
            logger.info(f'Skipping data file {file.name}')
            continue

        cwd = ROOT.gDirectory

        logger.info(f'Processing file {file.name}')

        infile = ROOT.TFile(str(file), "READ")
        intree = infile.Get(tree_name)
        orig_events = intree.GetEntries()
        logger.debug(f'Started with {orig_events} in the original tree')

        train_events = int(orig_events * train_probability)
        test_events = orig_events - train_events
        logger.debug(f'Splitting into {train_events} events for training and {test_events} events for testing')

        indexes = list(range(orig_events))
        train_event_list = random.sample(indexes, train_events)

        logger.debug('Setting up the files and trees')
        train_file = ROOT.TFile(str(train_path / file.name), "RECREATE")
        train_tree = intree.CloneTree(0)
        intree.CopyAddresses(train_tree)
        train_split_weight = array('f', [ float(train_factor + test_factor)/float(train_factor) ])
        train_tree.SetBranchAddress('splitFactor', train_split_weight)

        test_file = ROOT.TFile(str(test_path / file.name), "RECREATE")
        test_tree = intree.CloneTree(0)
        intree.CopyAddresses(test_tree)
        test_split_weight = array('f', [ float(train_factor + test_factor)/float(test_factor) ])
        test_tree.SetBranchAddress('splitFactor', test_split_weight)

        cwd.cd()

        logger.debug('Looping through events and sorting into respective trees')
        for evt in range(orig_events):
            intree.GetEntry(evt)

            if evt in train_event_list:
                train_tree.Fill()
            else:
                test_tree.Fill()

        train_file.cd()
        train_tree.Write()
        test_file.cd()
        test_tree.Write()

        test_file.Close()
        train_file.Close()

        infile.Close()

        cwd.cd()

def main():
    import argparse

    parser = argparse.ArgumentParser(
                    prog='split_train_test.py',
                    description='This script splits the root files from an input directory into the train and test datasets',
                    #epilog='Text at the bottom of help'
                    )

    parser.add_argument(
        '-i',
        '--inputPath',
        metavar = 'PATH',
        type = Path,
        help = 'Path to the directory containing all the root files.',
        required = True,
        #default = "./data",
        dest = 'input_path',
    )
    parser.add_argument(
        '-o',
        '--outputPath',
        metavar = 'PATH',
        type = Path,
        help = 'Path to the output directory. A Test subdirectory will be created for the Test files and a Train subdirectory for the Train files',
        required = True,
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
        '--testFactor',
        metavar = 'INT',
        type = int,
        help = 'The proportion of test events to train events, use both factors to specify the ratio, such as 10:1. Default: 1',
        default = 1,
        dest = 'test_factor',
    )
    parser.add_argument(
        '--trainFactor',
        metavar = 'INT',
        type = int,
        help = 'The proportion of train events to test events, use both factors to specify the ratio, such as 10:1. Default: 1',
        default = 1,
        dest = 'train_factor',
    )
    parser.add_argument(
        '-s'
        '--seed',
        metavar = 'INT',
        type = int,
        help = 'The seed to use for the random number generator. Default: None',
        default = None,
        dest = 'seed',
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

    script_main(input_path, output_path, args.tree_name, args.train_factor, args.test_factor, args.seed)

if __name__ == "__main__":
    main()