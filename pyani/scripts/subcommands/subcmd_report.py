#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""subcmd_report.py

Provides the report subcommand for pyani

(c) The James Hutton Institute 2017-18

Author: Leighton Pritchard
Contact: leighton.pritchard@hutton.ac.uk

Leighton Pritchard,
Information and Computing Sciences,
James Hutton Institute,
Errol Road,
Invergowrie,
Dundee,
DD6 9LH,
Scotland,
UK

The MIT License

Copyright (c) 2017-18 The James Hutton Institute

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

import os

import pandas as pd

from pyani import pyani_orm, pyani_report, pyani_db
from pyani.pyani_orm import Run, Genome, Comparison, Label, LabelMembership


def subcmd_report(args, logger):
    """Present report on ANI results and/or database contents.

    The report subcommand takes any of several long options that do one of two
    things:

    1. perform a single action.
    2. set a parameter/format

    These will typically take an output path to a file or directory into which
    the report will be written (whatever form it takes). By default, text
    output is written in plain text format, but for some outputs this can
    be modified by an 'excel' or 'html' format specifier, which writes outputs
    in that format, where possible.
    """
    # Output formats will apply across all tabular data requested
    # Expect comma-separated format arguments, and turn them into an iterable
    formats = ["tab"]
    if args.formats:
        formats += [fmt.strip() for fmt in args.formats.split(",")]
    formats = list(set(formats))  # remove duplicates
    logger.info("Creating output in formats: %s", formats)

    # Declare which database is being used, and connect to the session
    logger.info("Using database: %s", args.dbpath)
    session = pyani_orm.get_session(args.dbpath)

    # Report runs in the database
    if args.show_runs:
        outfname = os.path.join(args.outdir, "runs")
        logger.info("Writing table of pyani runs from the database to %s.*", outfname)
        statement = session.query(
            Run.run_id, Run.name, Run.method, Run.date, Run.cmdline
        ).statement
        data = pd.read_sql(statement, session.bind)
        headers = ["run ID", "name", "method", "date run", "command-line"]
        data.columns = headers
        pyani_report.write_dbtable(data, outfname, formats)

    # Report genomes in the database
    if args.show_genomes:
        outfname = os.path.join(args.outdir, "genomes")
        logger.info("Writing table of genomes from the database to %s.*", outfname)
        statement = session.query(
            Genome.genome_id,
            Genome.description,
            Genome.path,
            Genome.genome_hash,
            Genome.length,
        ).statement
        data = pd.read_sql(statement, session.bind)
        headers = ["genome ID", "description", "path", "MD5 hash", "genome length"]
        data.columns = headers
        pyani_report.write_dbtable(data, outfname, formats)

    # Report table of all genomes used for each run
    if args.show_runs_genomes:
        outfname = os.path.join(args.outdir, "runs_genomes")
        logger.info(
            "Writing table of pyani runs, with associated genomes " + "to %s.*",
            outfname,
        )
        # We query on the LabelMembership table, then join out to Run, Genome
        # and Label, so that we avoid multiple left joins
        statement = (
            session.query(
                LabelMembership.run_id,
                Run.name,
                Run.method,
                Run.date,
                LabelMembership.genome_id,
                Genome.description,
                Genome.path,
                Genome.genome_hash,
                Label.label,
                Label.class_label,
            )
            .join(Run, Genome, Label)
            .order_by(Run.run_id, Genome.genome_id)
            .statement
        )
        data = pd.read_sql(statement, session.bind)
        headers = [
            "run ID",
            "run name",
            "method",
            "date run",
            "genome ID",
            "genome description",
            "genome path",
            "genome hash",
            "genome label",
            "genome class",
        ]
        data.columns = headers
        pyani_report.write_dbtable(data, outfname, formats)

    # Report table of all runs in which a genome is involved
    if args.show_genomes_runs:
        outfname = os.path.join(args.outdir, "genomes_runs")
        logger.info(
            "Writing table of genomes, with associated pyani runs" + "to %s.*", outfname
        )
        # We query on the LabelMembership table, then join out to Run, Genome
        # and Label, so that we avoid multiple left joins
        statement = (
            session.query(
                LabelMembership.genome_id,
                Genome.description,
                Genome.path,
                Genome.genome_hash,
                Label.label,
                Label.class_label,
                LabelMembership.run_id,
                Run.name,
                Run.method,
                Run.date,
            )
            .join(Genome, Run, Label)
            .order_by(Genome.genome_id, Run.run_id)
            .statement
        )
        data = pd.read_sql(statement, session.bind)
        headers = [
            "genome ID",
            "genome description",
            "genome path",
            "genome hash",
            "genome label",
            "genome class",
            "run ID",
            "run name",
            "method",
            "date run",
        ]
        data.columns = headers
        pyani_report.write_dbtable(data, outfname, formats)

    # Report table of comparison results for the indicated runs
    if args.run_results:
        outfstem = os.path.join(args.outdir, "results")
        run_ids = [run_id.strip() for run_id in args.run_results.split(",")]
        logger.info("Attempting to write results tables for runs: %s", run_ids)
        for run_id in run_ids:
            outfname = "_".join([outfstem, str(run_id)])
            run_data = pyani_db.get_run(args.dbpath, run_id)
            logger.info("Collecting data for run with ID: %s (%s)", run_id, run_data[5])
            data = pyani_db.get_df_comparisons(args.dbpath, run_id)
            pyani_report.write_dbtable(data, outfname, formats)

    # Report matrices of comparison results for the indicated runs
    # For ANIm, all results other than coverage are symmetric matrices,
    # so we only get results in the forward direction.
    if args.run_matrices:
        outfstem = os.path.join(args.outdir, "matrix")
        run_ids = [run_id.strip() for run_id in args.run_matrices.split(",")]
        logger.info("Attempting to write results matrices for runs: %s", run_ids)
        for run_id in run_ids:
            logger.info("Extracting comparison results for run %s", run_id)
            results = pyani_db.ANIResults(args.dbpath, run_id)
            for matname, args in [
                ("identity", {"colour_num": 0.95}),
                ("coverage", {"colour_num": 0.95}),
                ("aln_lengths", {}),
                ("sim_errors", {}),
                ("hadamard", {}),
            ]:
                logger.info("Writing %s results", matname)
                outfname = "_".join([outfstem, matname, str(run_id)])
                pyani_report.write_dbtable(
                    getattr(results, matname),
                    outfname,
                    formats,
                    show_index=True,
                    **args
                )
