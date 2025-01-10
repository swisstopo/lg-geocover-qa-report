import click

from geocover_qa.config import QA_DIR
from geocover_qa.config import LOTS_IN_WORK


class PythonLiteralOption(click.Option):
    def type_cast_value(self, ctx, value):
        if value == "all":
            return None
        try:
            return ast.literal_eval(value)
        except:
            raise click.BadParameter(value)


# TODO: use plugins in this module and geocover_utils
@click.group()
def geocover222():
    """Geocover command line tools"""
    pass


@click.group()
def qa():
    """Quality Analysis commands for geocover"""
    click.echo("Running QA...")
    pass


@click.group()
def topology():
    """Run topology checks"""
    click.echo("Running topology checks...")


@qa.command(
    "stat",
    help="Analysis QA result GDB as plot/xlsx",
    context_settings={"show_default": True},
)
@click.option(
    "-d",
    "--qa-dir",
    default=QA_DIR,
    type=click.Path(exists=True, file_okay=True, dir_okay=True),
    help="QA test results directory (issue.gdb)",
)
@click.option(
    "-o",
    "--output-dir",
    default="outputs",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Output directory",
)
@click.option(
    "--rc",
    type=click.Choice(["2030-12-31", "2016-12-31"]),
    default="2030-12-31",
    help="Release",
)
@click.option(
    "-q",
    "--qa_name",
    type=click.Choice(["TechnicalQualityAssurance", "Topology"]),
    default="Topology",
    help="QA test name",
)
@click.option(
    "--dryrun", is_flag=True, default=False, help="Write the resulting images"
)
@click.option("--plots", is_flag=True, default=False, help="Display plot on the screen")
@click.option(
    "--start-date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Start date (YYYY-MM-DD).",
)
@click.option(
    "--end-date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="End date (YYYY-MM-DD).",
)
@click.option("--last", is_flag=True, help="Only process the most recent database.")
@click.option("--aggregate", is_flag=True, help="Aggregate data over the whole range.")
@click.option("--weekly", is_flag=True, help="Process data weekly.")
@click.option(
    "--regions",
    type=str,
    cls=PythonLiteralOption,
    default=LOTS_IN_WORK,
    help="Comma-separated list of regions to process. Use 'all' for no filter",
)
@click.option(
    "--output",
    type=click.Choice(["plots", "xlsx", "both"], case_sensitive=False),
    default="both",
    help="Output type.",
)
def stat(
    qa_dir,
    dryrun,
    plots,
    qa_name,
    start_date,
    end_date,
    last,
    rc,
    aggregate,
    weekly,
    regions,
    output,
    output_dir,
):
    # qa_name = "TechnicalQualityAssurance"
    # qa_name = "Topology"
    rc_name = None

    level, matched_values = check_qa_path_level(qa_dir)
    click.echo(f"Matched values: {matched_values}")
    click.echo(f"Level: {level}")

    if level == 3:
        if not rc:
            raise click.BadParameter(f"Option '--rc' is required for path {qa_dir}")
        else:
            full_qa_dir = os.path.join(qa_dir, rc)

    if level == 2:
        if not rc:
            raise click.BadParameter(f"Option '--rc' is required for path {qa_dir}")
        if not qa_name:
            raise click.BadParameter(
                f"Option '--qa-name' is required for path {qa_dir}"
            )

        full_qa_dir = os.path.join(qa_dir, qa_name, f"RC_{rc}")

    if level > 3:
        full_qa_dir = qa_dir
        if len(matched_values) == 2:
            qa_name, rc_name = matched_values

    if not os.path.exists(full_qa_dir):
        raise click.BadParameter(f"Path and options missmatch {full_qa_dir}")

    click.echo(f"Final path is valid: {full_qa_dir}")

    if rc:
        click.echo(f"RC: {rc}")
    if qa_name:
        click.echo(f"QA Name: {qa_name}")
    click.echo(end_date)

    if rc_name is None:
        rc_name = f"RC_{rc}"

    GROUP_BY = ["Id", "IssueType", "Code", "CodeDescription", "QualityCondition"]
    #
    # TOD: test if qa_dir is already an issue db

    if not os.path.isdir(output_dir):
        os.makedirs(output_dir)

    if full_qa_dir.endswith("issue.gdb"):
        meta = parse_qa_full_path(qa_dir, rc_name, qa_name)

        if meta:
            issue_gdbs = [meta]
    else:
        issue_gdbs = get_qa_gdb(
            qa_name=qa_name,
            base_dir=qa_dir,
            release=rc_name,
            start_date=start_date,
            end_date=end_date,
            last=last,
        )
    # Display the found files with parsed dates
    issue_gdbs_nb = len(issue_gdbs)
    logger.info(f"Found: {issue_gdbs_nb}")

    logger.debug(
        f"Found: {json.dumps(issue_gdbs, indent=4, sort_keys=True, default=str)}"
    )

    lots_in_work = regions

    click.echo(lots_in_work)

    GPKG_FILEPATH = os.path.join(cur_dir, "../../../../QA/data/lots_mapsheets.gpkg")
    ch_gdf = gpd.read_file(GPKG_FILEPATH, layer="ch")
    ch_gdf = ch_gdf.set_crs(epsg=2056, allow_override=True)
    lots_perimeter_gdf = get_lots_perimeter(GPKG_FILEPATH)
    ALL_SWITZERLAND_ID = "CH"

    stats_over_time = []

    if start_date is None:
        start_date = min(issue_gdbs, key=lambda x: x["date"])["date"]
    if end_date is None:
        end_date = max(issue_gdbs, key=lambda x: x["date"])["date"]

    for idx, entry in enumerate(issue_gdbs):
        logger.info(
            f"{idx}/{issue_gdbs_nb} Date: {entry['date']}, File Path: {entry['file_path']}"
        )

        issue_gdb_path = entry["file_path"]
        file_date = entry["date"]
        rc = entry["RC"]
        test_name = entry["QA"]

        plot_single_lot(ALL_SWITZERLAND_ID, lots_perimeter_gdf, issue_gdb_path, ch_gdf)

        combined_issues, stats = get_stats(issue_gdb_path, group_by=GROUP_BY)

        if stats is None:
            continue

        logger.info(type(stats))

        if lots_in_work is None:
            lots_in_work = stats["Lot"].unique()

        grouped_stats = stats[stats["Lot"].isin(lots_in_work)]

        # Display grouped stats
        logger.info(grouped_stats.head())

        # Append the statistics along with the date
        stats_over_time.append({"date": file_date, "stats": grouped_stats})

        # Save the statistics to CSV
        # grouped_stats.to_csv("lots_issue_stats.csv", index=False)

        if any(ele in output for ele in ["xlsx", "both"]):
            xlsx_path = os.path.join(
                output_dir, f"{file_date:%Y-%m-%d}_{rc}_{test_name}.xlsx"
            )

            with pd.ExcelWriter(xlsx_path) as writer:
                # writing to the 'Employee' sheet
                grouped_stats.to_excel(writer, sheet_name="Issue", index=False)

                # Get the xlsxwriter objects from the dataframe writer object.
                workbook = writer.book
                worksheet = writer.sheets["Issue"]

                # Set the width of columns A to D to 20
                # worksheet.set_column("C:E", 50)

    # Plot the evolution of issues over time
    # Apply a logarithmic scale to the y-axis

    if any(ele in output for ele in ["plot", "both"]):
        # Combine statistics over time for plotting
        all_stats = pd.concat(
            [entry["stats"].assign(date=entry["date"]) for entry in stats_over_time],
            ignore_index=True,
        )

        # Pivot the data for easier plotting (issue_count by Lot and date)
        pivot_stats = all_stats.pivot_table(
            index="date",
            columns=[
                "Lot",
                "IssueType",
            ],  # , "Code", "CodeDescription", "QualityCondition"],
            values="issue_count",
            aggfunc="sum",
            fill_value=0,
        )

        # Plot the evolution of issues over time with a logarithmic y-axis
        ax = pivot_stats.plot(kind="line", marker="o", figsize=(12, 6))

        # Set x and y labels and title
        plt.xlabel("Date")
        plt.ylabel("Number of Issues (Log Scale)")
        plt.title(
            f"Evolution of {test_name} issues Over Time by Lot and Issue Type ({rc})"
        )

        # Apply a logarithmic scale to the y-axis
        if qa_name == "Topology":
            plt.yscale("log")
        plt.ylim(bottom=0)  # this line

        # Adjust legend and layout
        # plt.legend(title="Lot & Issue Type", bbox_to_anchor=(1.05, 1), loc="upper left")
        # plt.legend(loc='upper left', borderpad=1.5, labelspacing=1.5)
        # Extract and customize the labels
        # Example: Using only "Lot" and "IssueType"
        custom_labels = [
            f"{lot} - {issue_type}" for lot, issue_type, *_ in pivot_stats.columns
        ]

        # Update the legend
        # ax.legend(custom_labels, title="Lot - IssueType", bbox_to_anchor=(1.05, 1), loc='upper left')
        ax.legend(
            custom_labels,
            title="Lot - Code",
            bbox_to_anchor=(1.05, 1),
            loc="upper left",
            fontsize="small",
        )
        plt.subplots_adjust(right=0.6)
        # plt.tight_layout()

        # Display the plot
        if not dryrun:
            if start_date != end_date:
                date_str = f"{start_date:%Y-%m-%d}_{start_date:%Y-%m-%d}"
            else:
                date_str = f"{start_date:%Y-%m-%d}"
            plot_name = f"{date_str}_{rc}_{test_name}"
            plot_path = os.path.join(output_dir, plot_name)
            logger.info(f"Save fig to '{plot_path}'")
            plt.savefig(plot_path, dpi=100)
        if plots:
            plt.show()
