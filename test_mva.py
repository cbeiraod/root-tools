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

def script_main(
                input_file: Path,
                weight_file: Path,
                variable_file: Path,
                output_path: Path,
                tree_name: str = "bdttree",
                variable_name: str = "BDT",
                ):
    logger = logging.getLogger('test_mva')

    variables = {}

    logger.info("Reding variables from YAML file")
    with variable_file.open("r") as file_stream:
        yaml_info = yaml.safe_load(file_stream)

        if "variables" not in yaml_info:
            logger.error("The yaml file does not contain any variable information")
            return

        for var in yaml_info["variables"]:
            variables[var] = array('f', [ 0 ])

    with ROOT.TFile(str(input_file), "READ") as root_file:
        if root_file.IsZombie():
            print("The ROOT file is not a ROOT file")
            return

        intree = root_file.Get(tree_name)

        testMVA = array('f', [ 0 ])
        for key in variables:
            intree.SetBranchAddress(key, variables[key])
        if variable_name is not None and variable_name != "":
            intree.SetBranchAddress(variable_name, testMVA)

        reader = ROOT.TMVA.Reader( "!Color:!Silent" )

        for variable in variables:
            reader.AddVariable(variable, variables[variable])

        reader.BookMVA("MVA", str(weight_file))

        mva_histogram = ROOT.TH1D("mva_hist", "MVA Histogram", 2000, -1, 1)
        diff_histogram = ROOT.TH1D("diff_mva_hist", "MVA Difference Histogram", 2000, -.0000001, .0000001)

        orig_events = intree.GetEntries()
        for evt in range(orig_events):
            intree.GetEntry(evt)

            calculated_mva = reader.EvaluateMVA("MVA")
            mva_histogram.Fill(calculated_mva)

            if variable_name is not None and variable_name != "":
                mva_diff = calculated_mva - testMVA[0]
                diff_histogram.Fill(mva_diff)


        canvas = ROOT.TCanvas("Canv", "Canv", 800, 600)

        mva_histogram.SaveAs(str(output_path/"mva_hist.C"))
        mva_histogram.Draw()
        canvas.SaveAs(str(output_path/"mva_hist.png"))

        if variable_name is not None and variable_name != "":
            diff_histogram.SaveAs(str(output_path/"diff_mva_hist.C"))
            diff_histogram.Draw()
            canvas.SaveAs(str(output_path/"diff_mva_hist.png"))

def main():
    import argparse

    parser = argparse.ArgumentParser(
                    prog='test_mva.py',
                    description='Test TMVA MVA evaluation on a ROOT file and optionally compare against a branch in the file',
                    #epilog='Text at the bottom of help'
                    )

    parser.add_argument(
        '-i',
        '--inputFile',
        metavar = 'FILE',
        type = Path,
        help = 'Path to the ROOT file to test the MVA on.',
        required = True,
        #default = "./data",
        dest = 'input_file',
    )
    parser.add_argument(
        '-w',
        '--weightFile',
        metavar = 'FILE',
        type = Path,
        help = 'Path to the TMVA weight file with the MVA weights.',
        required = True,
        #default = "./data",
        dest = 'weight_file',
    )
    parser.add_argument(
        '-y',
        '--variableFile',
        metavar = 'FILE',
        type = Path,
        help = 'Path to the YAML file with the variables to use in the MVA.',
        required = True,
        #default = "./data",
        dest = 'variable_file',
    )
    parser.add_argument(
        '-o',
        '--outputPath',
        metavar = 'PATH',
        type = Path,
        help = 'Path to the output directory where plots will be saved.',
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
        '-v',
        '--variableName',
        metavar = 'STR',
        type = str,
        help = 'Name of the variable to check in the tree. Default: BDT',
        default = 'BDT',
        dest = 'variable_name',
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

    input_file: Path = args.input_file
    if not input_file.exists() or not input_file.is_file():
        raise RuntimeError("The input file does not exist or is not a file")
    input_file = input_file.absolute()

    weight_file: Path = args.weight_file
    if not weight_file.exists() or not weight_file.is_file():
        raise RuntimeError("The weight file does not exist or is not a file")
    weight_file = weight_file.absolute()

    variable_file: Path = args.variable_file
    if not variable_file.exists() or not variable_file.is_file():
        raise RuntimeError("The weight file does not exist or is not a file")
    variable_file = variable_file.absolute()

    output_path: Path = args.output_path
    if not output_path.exists() or not output_path.is_dir():
        logging.error("You must define a valid data output path")
        exit(1)
    output_path = output_path.absolute()

    script_main(input_file, weight_file, variable_file, output_path, args.tree_name, args.variable_name)

if __name__ == "__main__":
    main()