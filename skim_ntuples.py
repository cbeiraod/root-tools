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
import random
from array import array
import yaml

def script_main(
                input_path: Path,
                output_path: Path,
                yaml_file: Path,
                ):
    logger = logging.getLogger('skim_ntuples')

    logger.info("Reading information from YAML file")
    with yaml_file.open("r") as file_stream:
        yaml_info = yaml.safe_load(file_stream)

        seed = yaml_info["seed"]

        input_ttree_name  = yaml_info["input_ttree"]
        output_ttree_name = yaml_info["output_ttree"]
        do_reinterpret = yaml_info["do_reinterpret"]
        do_filter = yaml_info["filter"]
        branches = yaml_info["branches"]

        if do_filter is not False:
            filter_events = do_filter
            do_filter = True
        else:
            filter_events = None

    if seed is not None:
        random.seed(seed)

    for file in input_path.iterdir():
        if not file.is_file():
            continue
        if not file.suffix == ".root":
            continue

        cwd = ROOT.gDirectory

        logger.info(f'Processing file {file.name}')

        infile = ROOT.TFile(str(file), "READ")
        intree = infile.Get(input_ttree_name)
        intree.SetBranchStatus("*", 0) # Disable all branches, then only enable the ones we want/need
        orig_events = intree.GetEntries()
        logger.debug(f'Started with {orig_events} in the original tree')

        if do_filter:
            logger.debug(f'Filtering into {filter_events} events')
            indexes = list(range(orig_events))
            filter_event_list = random.sample(indexes, filter_events)
        else:
            filter_event_list = []

        logger.debug("Enabling the branches we want to keep")
        for bname in branches:
            intree.SetBranchStatus(bname, 1)

        logger.debug('Setting up the output files and trees')
        outfile = ROOT.TFile(str(output_path / file.name), "RECREATE")
        #default: 75600
        #outfile.SetCompressionLevel(9) # 71688
        outfile.SetCompressionAlgorithm(ROOT.RCompressionSetting.EAlgorithm.EValues.kLZMA)
        #outfile.SetCompressionLevel(0) # 198352
        #outfile.SetCompressionLevel(1) # 70760
        #outfile.SetCompressionLevel(2) # 70456
        #outfile.SetCompressionLevel(3) # 70096
        #outfile.SetCompressionLevel(4) # 69752
        #outfile.SetCompressionLevel(5) # 69712
        #outfile.SetCompressionLevel(6) # 68768
        #outfile.SetCompressionLevel(7) # 68768 69648 108568
        #outfile.SetCompressionLevel(8) # 69712
        outfile.SetCompressionLevel(9) # 69712 69752 108624

        #outtree = intree.CloneTree(0)
        #outtree.SetName(output_ttree_name)
        #outtree.SetTitle(output_ttree_name)
        #for bname in branches:
        #    if branches[bname]['rename'] != False: # This renaming kind of worked, but not 100%, so use the below
        #        this_bname = branches[bname]['rename']

        #        br = outtree.GetBranch(bname)
        #        br.SetName(this_bname)

        outtree = ROOT.TTree(output_ttree_name, output_ttree_name)
        for bname in branches:
            branch_type = None
            leaf_type = None
            type_name = intree.GetLeaf(bname).GetTypeName()
            if type_name == "Float_t":
                branch_type = 'f'
                leaf_type = "F"
            elif type_name == "Double_t":
                branch_type = 'd'
                leaf_type = "D"
            elif type_name == "UInt_t":  # 4 bytes
                branch_type = 'L'
                leaf_type = "i"
            elif type_name == "ULong64_t":  # 8 bytes
                branch_type = 'Q'
                leaf_type = "l"

            if branch_type is None:
                logger.error(f"Unknown branch type for branch {bname}, type: {type_name}")
                continue

            branches[bname]["var"] = array(branch_type, [ 0 ])

            this_bname = bname
            if branches[bname]['rename'] != False:
                this_bname = branches[bname]['rename']
            outtree.Branch(this_bname, branches[bname]["var"], this_bname + "/" + leaf_type)

            intree.SetBranchAddress(bname, branches[bname]["var"])

        cwd.cd()

        logger.debug('Looping through events and sorting into respective trees')
        for evt in range(orig_events):
            if not do_filter or evt in filter_event_list:
                intree.GetEntry(evt)

                if do_reinterpret:
                    for bname in branches:
                        if "reinterpret" in branches[bname] and branches[bname]["reinterpret"] is not False:
                            if branches[bname]["var"][0] == -9999.0:
                                branches[bname]["var"][0] = branches[bname]["reinterpret"]

                outtree.Fill()

        outfile.cd()
        outtree.Write()
        outfile.Close()

        infile.Close()

        cwd.cd()

def main():
    import argparse

    parser = argparse.ArgumentParser(
                    prog='skim_ntuples.py',
                    description='This script skims the ntuples contained in a directory. A YAML file is used to control the skimming parameters, i.e. which branches to keep. It is also possible to rename branches and to set a filter on the events if desired',
                    #epilog='Text at the bottom of help'
                    )

    parser.add_argument(
        '-i',
        '--inputPath',
        metavar = 'PATH',
        type = Path,
        help = 'Path to the directory containing all the root nTuple files.',
        required = True,
        #default = "./data",
        dest = 'input_path',
    )
    parser.add_argument(
        '-o',
        '--outputPath',
        metavar = 'PATH',
        type = Path,
        help = 'Path to the output directory where to store the skimmed nTuples',
        required = True,
        dest = 'output_path',
    )
    parser.add_argument(
        '-y',
        '--yamlFile',
        metavar = 'FILE',
        type = Path,
        help = 'Path to the YAML file describing the skim operation to be performed.',
        required = True,
        #default = "./data",
        dest = 'yaml_file',
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

    yaml_file: Path = args.yaml_file
    if not yaml_file.exists() or not yaml_file.is_file():
        raise RuntimeError("The mva file does not exist or is not a file")
    yaml_file = yaml_file.absolute()

    script_main(input_path, output_path, yaml_file)

if __name__ == "__main__":
    main()
