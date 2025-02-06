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
from array import array
from dataclasses import dataclass

@dataclass
class Point:
    x: float
    y: float
    z: float = 0.0

p = Point(1.5, 2.5)

@dataclass
class EventID:
    run: int
    lumi: int
    evt: int
    isTrain: bool
    isTest: bool

def script_main(
                input_path: Path,
                train_path: Path,
                test_path: Path,
                output_path: Path,
                tree_name: str = "bdttree",
                split_tree_name: str = "bdttree",
                ):
    logger = logging.getLogger('apply_pre_splitting')

    for file in input_path.iterdir():
        if not file.is_file():
            continue
        if not file.suffix == ".root":
            continue

        # Skip data samples
        if file.name[:4] == "Data":
            logger.info(f'Skipping data file {file.name}')
            continue

        cwd = ROOT.gDirectory

        logger.info(f'Processing file {file.name}')

        trainFile = train_path/file.name
        testFile  = test_path/file.name
        splitFile = output_path/file.name

        logger.debug("Fetching the pre-split train and test trees")
        if not trainFile.exists() or not trainFile.is_file():
            logger.warning(f"The pre-split train file for {file.name} does not exist, skipping it")
            continue
        if not testFile.exists() or not testFile.is_file():
            logger.warning(f"The pre-split test file for {file.name} does not exist, skipping it")
            continue
        trainEventsFile = ROOT.TFile(str(trainFile), "READ")
        testEventsFile  = ROOT.TFile(str(testFile), "READ")

        inTrainTree = trainEventsFile.Get(split_tree_name)
        inTestTree  = testEventsFile.Get(split_tree_name)

        inTrainTree.SetBranchStatus("*", 0)
        inTrainTree.SetBranchStatus("Run", 1)
        inTrainTree.SetBranchStatus("Event", 1)
        inTrainTree.SetBranchStatus("LumiSec", 1)
        inTestTree.SetBranchStatus("*", 0)
        inTestTree.SetBranchStatus("Run", 1)
        inTestTree.SetBranchStatus("Event", 1)
        inTestTree.SetBranchStatus("LumiSec", 1)

        Run = array('L', [0])
        Event = array('Q', [0])
        LumiSec = array('L', [0])

        inTestTree.SetBranchAddress("Run", Run)
        inTestTree.SetBranchAddress("Event", Event)
        inTestTree.SetBranchAddress("LumiSec", LumiSec)
        inTrainTree.SetBranchAddress("Run", Run)
        inTrainTree.SetBranchAddress("Event", Event)
        inTrainTree.SetBranchAddress("LumiSec", LumiSec)

        eventList = []

        logger.debug("Caching the pre-split data")
        trainEntries = inTrainTree.GetEntries()
        for evt in range(trainEntries):
            inTrainTree.GetEntry(evt)
            eventList.append(EventID(Run[0], LumiSec[0], Event[0], True, False))

        testEntries = inTestTree.GetEntries()
        for evt in range(testEntries):
            inTestTree.GetEntry(evt)
            eventList.append(EventID(Run[0], LumiSec[0], Event[0], False, True))

        logger.debug("Loading input file")
        infile = ROOT.TFile(str(file), "READ")
        intree = infile.Get(tree_name)
        orig_events = intree.GetEntries()
        logger.debug(f"There are {orig_events} events to split")

        intree.SetBranchStatus("*", 0)
        intree.SetBranchStatus("Run", 1)
        intree.SetBranchStatus("Event", 1)
        intree.SetBranchStatus("LumiSec", 1)

        intree.SetBranchAddress("Run", Run)
        intree.SetBranchAddress("Event", Event)
        intree.SetBranchAddress("LumiSec", LumiSec)

        logger.debug("Creating output file and ttree")
        splitEventsFile = ROOT.TFile(str(splitFile), "RECREATE")
        splitTree = ROOT.TTree(tree_name, tree_name)
        isTest = array('B', [0])  # Using an unsigned char to store boolean data
        isTrain = array('B', [0])

        splitTree.Branch("Run", Run, "Run/i")
        splitTree.Branch("Event", Event, "Event/l")
        splitTree.Branch("LumiSec", LumiSec, "LumiSec/i")
        splitTree.Branch("isTrain", isTrain, "isTrain/b")  # also unsigned char, the root definition and array definition do not match
        splitTree.Branch("isTest", isTest, "isTest/b")

        cwd.cd()

        def search(run, lumisection, event, event_list):
            return [element for element in event_list if element.evt == event]

        logger.debug('Looping through events and sorting into respective categories')
        fileNotSplit = False
        evtCount = 0
        for evt in range(orig_events):
            if evtCount%1000 == 0:
                logger.debug(f"Processing event {evtCount}")
            evtCount += 1
            intree.GetEntry(evt)

            isTest[0] = 0
            isTrain[0] = 0

            #matches = list(filter(lambda evt: evt.evt == intree.Event, eventList))
            #matches = list(filter(lambda evt: evt.evt == Event[0], eventList))
            matches = search(Run[0], LumiSec[0], Event[0], eventList)

            #matches = list(filter(lambda evt: (evt.run == intree.Run) and (evt.lumi == intree.LumiSec) and (evt.evt == intree.Event), eventList))
            if len(matches) == 2:
                logger.warning(f"The file {file.name} was not split in the previous split, skipping it")
                fileNotSplit = True
                break

            if len(matches) > 2:
                logger.error(f"Multiple matches found, more than expected. This is a problem!!! File: {file.name}")
                return

            if len(matches) == 1:
                isTest[0] = matches[0].isTest
                isTrain[0] = matches[0].isTrain
            splitTree.Fill()


        splitEventsFile.cd()
        splitTree.Write()
        splitEventsFile.Close()

        if fileNotSplit:
            splitFile.unlink()

        infile.Close()

        cwd.cd()

def main():
    import argparse

    parser = argparse.ArgumentParser(
                    prog='apply_pre_splitting.py',
                    description='This script applies an existing splitting to the current ntuples',
                    #epilog='Text at the bottom of help'
                    )

    parser.add_argument(
        '-i',
        '--inputPath',
        metavar = 'PATH',
        type = Path,
        help = 'Path to the directory containing all the root ntuple files.',
        required = True,
        #default = "./data",
        dest = 'input_path',
    )
    parser.add_argument(
        '--trainPath',
        metavar = 'PATH',
        type = Path,
        help = 'Path to the directory containing the pre-split train nTuples',
        required = True,
        dest = 'train_path',
    )
    parser.add_argument(
        '--testPath',
        metavar = 'PATH',
        type = Path,
        help = 'Path to the directory containing the pre-split test nTuples',
        required = True,
        dest = 'test_path',
    )
    parser.add_argument(
        '-o',
        '--outputPath',
        metavar = 'PATH',
        type = Path,
        help = 'Path to the output directory, where the splitting trees will be saved',
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
        '--splitTreeName',
        metavar = 'STR',
        type = str,
        help = 'Name of the tree contained in the pre-splitted root files. Default: bdttree',
        default = 'bdttree',
        dest = 'split_tree_name',
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

    train_path: Path = args.train_path
    if not train_path.exists():
        raise RuntimeError("The train path does not exist")
    train_path = train_path.absolute()

    test_path: Path = args.test_path
    if not test_path.exists():
        raise RuntimeError("The test path does not exist")
    test_path = test_path.absolute()

    output_path: Path = args.output_path
    if not output_path.exists() or not output_path.is_dir():
        logging.error("You must define a valid data output path")
        exit(1)
    output_path = output_path.absolute()

    script_main(input_path, train_path, test_path, output_path, args.tree_name, args.split_tree_name)

if __name__ == "__main__":
    main()