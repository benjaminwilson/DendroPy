#! /usr/bin/env python


import os
import sys
import optparse
import dendropy
from cStringIO import StringIO
from dendropy.utility.messaging import ConsoleMessenger
from dendropy.utility.cli import confirm_overwrite, show_splash
from dendropy import prometry

_program_name = "Alignment-Prometry"
_program_subtitle = "Alignment profile distance calculator"
_program_date = "Mar 02 2013"
_program_version = "Version 1.0.0 (%s)" % _program_date
_program_author = "Jeet Sukumaran"
_program_contact = "jeetsukumaran@gmail.com"
_program_copyright = "Copyright (C) 2013 Jeet Sukumaran.\n" \
                 "License GPLv3+: GNU GPL version 3 or later.\n" \
                 "This is free software: you are free to change\nand redistribute it. " \


def calc_alignment_profile(char_matrix,
        normalize_to_num_comps=True,
        ignore_uncertain=True):
    state_alphabet = dendropy.DNA_STATE_ALPHABET
    char_vectors = [v for v in char_matrix.taxon_seq_map.values()]
    diffs = []
    for vidx, i in enumerate(char_vectors[:-1]):
        for j in char_vectors[vidx+1:]:
            if len(i) != len(j):
                raise Exception("sequences of unequal length")
            diff = 0
            counted = 0
            for cidx, c in enumerate(i):
                c1 = c
                c2 = j[cidx]
                if (not ignore_uncertain) \
                    or (c1.value is not state_alphabet.gap \
                        and c2.value is not state_alphabet.gap \
                        and len(c1.value.fundamental_ids) == 1 \
                        and len(c2.value.fundamental_ids) == 1):
                    counted += 1
                    if c1.value is not c2.value:
                        diff += 1
            if normalize_to_num_comps:
                diff = float(diff)/counted
            diffs.append(diff)
    return sorted(diffs)

def calc_alignment_profile(char_matrix,
        normalize_to_num_comps=True,
        ignore_uncertain=True):
    state_alphabet = dendropy.DNA_STATE_ALPHABET
    diffs = {}
    for a in state_alphabet:
        for b in state_alphabet:
            diffs[frozenset([a,b])] = 0
    char_vectors = [v for v in char_matrix.taxon_seq_map.values()]
    for vidx, i in enumerate(char_vectors[:-1]):
        for j in char_vectors[vidx+1:]:
            if len(i) != len(j):
                raise Exception("sequences of unequal length")
            # diff = 0
            # counted = 0
            for cidx, c in enumerate(i):
                c1 = c
                c2 = j[cidx]
                if (not ignore_uncertain) \
                    or (c1.value is not state_alphabet.gap \
                        and c2.value is not state_alphabet.gap \
                        and len(c1.value.fundamental_ids) == 1 \
                        and len(c2.value.fundamental_ids) == 1):
                    # counted += 1
                    if c1.value is not c2.value:
                        diffs[frozenset([c1.value, c2.value])] += 1
            # if normalize_to_num_comps:
                # diff = float(diff)/counted
            # diffs.append(diff)
    return sorted(diffs.values())

def read_alignments(
        filepaths,
        schema,
        normalize_to_num_comps,
        messenger):
    messenger.send_info("Running in serial mode.")

    taxon_set = dendropy.TaxonSet()

    messenger.send_info("%d source(s) to be processed." % len(filepaths))

    profile_matrices = []
    hamming_distances = prometry.ProfileMatrix("Hamming.Distance")
    profile_matrices.append(hamming_distances)

    for fidx, fpath in enumerate(filepaths):
        messenger.send_info("Processing %d of %d: '%s'" % (fidx+1, len(filepaths), fpath), wrap=False)
        aln = dendropy.DnaCharacterMatrix.get_from_path(fpath,
                schema=schema,
                taxon_set=taxon_set)
        label = "Alignment {}".format(fidx+1)
        data = calc_alignment_profile(char_matrix=aln,
                normalize_to_num_comps=normalize_to_num_comps,
                ignore_uncertain=True)
        hamming_distances.add(
                index=fidx+1,
                label=label,
                profile_data=data)

    messenger.send_info("Serial processing of %d source(s) completed." % len(filepaths))
    return profile_matrices


def main_cli():

    description =  "%s %s %s" % (_program_name, _program_version, _program_subtitle)
    usage = "%prog [options] SEQ-FILE [SEQ-FILE [SEQ-FILE [...]]"

    parser = optparse.OptionParser(usage=usage,
            add_help_option=True,
            version = _program_version,
            description=description)

    source_optgroup = optparse.OptionGroup(parser, "Source Options")
    parser.add_option_group(source_optgroup)
    source_optgroup.add_option("--format",
            dest="schema",
            default="dnafasta",
            help="format for data (default='%default')")

    metrics_optgroup = optparse.OptionGroup(parser, "Metric Options")
    parser.add_option_group(metrics_optgroup)
    metrics_optgroup.add_option("--normalize-to-number-of-comparisons",
            dest="normalize_to_num_comps",
            action="store_true",
            default=False,
            help="normalize raw pairwise difference counts to number of bases of compared for every pair of sequences")

    run_optgroup = optparse.OptionGroup(parser, "Program Run Options")
    parser.add_option_group(run_optgroup)
    run_optgroup.add_option("-q", "--quiet",
            action="store_true",
            dest="quiet",
            default=False,
            help="suppress ALL logging, progress and feedback messages")

    (opts, args) = parser.parse_args()

    (opts, args) = parser.parse_args()
    if opts.quiet:
        messaging_level = ConsoleMessenger.ERROR_MESSAGING_LEVEL
    else:
        messaging_level = ConsoleMessenger.INFO_MESSAGING_LEVEL
    messenger = ConsoleMessenger(name="Alignment-Prometry", messaging_level=messaging_level)

    # splash
    if not opts.quiet:
        show_splash(prog_name=_program_name,
                prog_subtitle=_program_subtitle,
                prog_version=_program_version,
                prog_author=_program_author,
                prog_copyright=_program_copyright,
                dest=sys.stderr,
                extended=False)

    filepaths = []
    if len(args) > 0:
        for fpath in args:
            fpath = os.path.expanduser(os.path.expandvars(fpath))
            if not os.path.exists(fpath):
                messenger.send_error("Terminating due to missing file: '{}'".format(fpath))
                sys.exit(1)
            else:
                filepaths.append(fpath)
        if len(filepaths) == 0:
            messenger.send_error("No valid sources of alignments specified.")
            sys.exit(1)
        elif len(filepaths) == 1:
            messenger.send_error("At least two sources of alignments must be specified.")
            sys.exit(1)
    else:
        messenger.send_info("No sources of alignments specified.")
        sys.exit(1)

    profiles = read_alignments(
            filepaths=filepaths,
            schema=opts.schema,
            normalize_to_num_comps=opts.normalize_to_num_comps,
            messenger=messenger,
            )

    prometry.summarize_profile_matrices(profiles, sys.stdout)

if __name__ == "__main__":
    main_cli()