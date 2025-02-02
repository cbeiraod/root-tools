# root-tools

This is a collection of scripts I have written over time to handle root files, typically within the context of a physics analysis where a bunch of root files need to be handled together in batches.

## How To Run

I recommend using a venv. Set it up with: `python3 -m venv venv`
This will create a venv directory called venv.

Then activate the venv with: `. venv/bin/activate`

Then install the dependencies, such as natsort:

```
python -m pip install natsort
```

On macOS, we need to "re-enable" ROOT inside the venv. On my system, using zsh, I had to run the following command:
`pushd /usr/local >/dev/null; . bin/thisroot.sh; popd >/dev/null`
Use the equivalent thisroot script for your environment instead.
