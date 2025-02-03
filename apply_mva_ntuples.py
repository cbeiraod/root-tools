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
import yaml

# For figuring out branch types in a tree: bdttree->GetLeaf("Jet1Pt")->GetTypeName()

def script_main(
                input_path: Path,
                mva_file: Path,
                output_path: Path,
                weight_path: Path,
                tree_name: str = "bdttree",
                ):
    logger = logging.getLogger('apply_mva_ntuples')

    logger.info("Reading information from MVA YAML file")
    with mva_file.open("r") as file_stream:
        mva_info = yaml.safe_load(file_stream)

        logger.info("Fetching variable list and building TMVA readers")
        variables = {}
        for mva in mva_info:
            mva_info[mva]["reader"] = ROOT.TMVA.Reader( "Color:!Silent" )
            for variable in mva_info[mva]['variables']:
                if variable not in variables:
                    variables[variable] = array('f', [ 0 ])
                mva_info[mva]["reader"].AddVariable(variable, variables[variable])

            weight_file = mva_info[mva]["weights"]
            if weight_file[0] != '/':
                weight_file = weight_path / weight_file
            else:
                weight_file = Path(weight_file)

            mva_info[mva]["reader"].BookMVA(mva, str(weight_file))

            mva_info[mva]["mva"] = array('f', [ 0 ])

    for file in input_path.iterdir():
        if not file.is_file():
            continue
        if not file.suffix == ".root":
            continue

        cwd = ROOT.gDirectory

        logger.info(f'Processing file {file.name}')

        infile = ROOT.TFile(str(file), "READ")
        intree = infile.Get(tree_name)
        orig_events = intree.GetEntries()

        intree.SetBranchStatus("*", 0)
        for key in variables:
            intree.SetBranchStatus(key, 1)
            intree.SetBranchAddress(key, variables[key])

        outfile = ROOT.TFile(str(output_path / file.name), "RECREATE")
        outtree = ROOT.TTree(tree_name, tree_name)
        for mva in mva_info:
            outtree.Branch(mva, mva_info[mva]['mva'], mva+'/F')

        cwd.cd()

        logger.debug('Looping through events and computing the MVAs')
        for evt in range(orig_events):
            intree.GetEntry(evt)

            for mva in mva_info:
                mva_info[mva]['mva'][0] = mva_info[mva]['reader'].EvaluateMVA(mva)

            outtree.Fill()

        outfile.cd()
        outtree.Write()
        outfile.Close()

        infile.Close()

        cwd.cd()

def main():
    import argparse

    parser = argparse.ArgumentParser(
                    prog='apply_mva_ntuples.py',
                    description='This script applies TMVA MVAs to a set of nTuples in a directory. The TMVA algorithms are described in an accessory yaml file and more than one algorithm may be specified.',
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
        '-m',
        '--mvaFile',
        metavar = 'FILE',
        type = Path,
        help = 'Path to the YAML file with the MVA algorithms to apply.',
        required = True,
        #default = "./data",
        dest = 'mva_file',
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
        '-w',
        '--weightPath',
        metavar = 'PATH',
        type = Path,
        help = 'Path to use as the base path for the weight files, if they are not absolute.',
        default = "./",
        dest = 'weight_path',
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

    weight_path: Path = args.weight_path
    if not weight_path.exists():
        raise RuntimeError("The weight path does not exist")
    weight_path = weight_path.absolute()

    mva_file: Path = args.mva_file
    if not mva_file.exists() or not mva_file.is_file():
        raise RuntimeError("The mva file does not exist or is not a file")
    mva_file = mva_file.absolute()

    output_path: Path = args.output_path
    if not output_path.exists() or not output_path.is_dir():
        logging.error("You must define a valid data output path")
        exit(1)
    output_path = output_path.absolute()

    script_main(input_path, mva_file, output_path, weight_path, args.tree_name)

if __name__ == "__main__":
    main()