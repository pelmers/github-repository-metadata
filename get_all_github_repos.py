#!/usr/bin/env python

# get_all_top_repos: get metadata on all repositories in github*
# * with at least 5 stars
# output in json format to given file name

import argparse
import json
import requests
import time
import os
import pickle

import datetime
from tqdm import tqdm

from functools import reduce

# Resolve to relative path to this script file
r = lambda p: os.path.join(os.path.abspath(os.path.dirname(__file__)), *p.split("/"))

# README: get the token from here, https://github.com/settings/tokens
# put it in a file "github_token" in the same folder
GITHUB_TOKEN = open(r("github_token")).read().strip()

# We use this config unless resume is specified (in which case we load from the pickle file)
DEFAULT_CONFIG = {
    "star_range": [5, 1000000],
    "date_range": [datetime.datetime(2009, 1, 1), datetime.datetime.today()],
}


def get_output_filename(config):
    return f"repos_{config['date_range'][0].date()}_{config['date_range'][1].date()}_stars_{config['star_range'][0]}_{config['star_range'][1]}.json"


# Taken from https://github.com/EvanLi/Github-Ranking/blob/master/source/common.py
# permalink: https://github.com/EvanLi/Github-Ranking/blob/b8531b18647dbccc8d2e1fb1d6ef6c02871271ae/source/common.py
def get_graphql_data(GQL, retries=5):
    """
    use graphql to get data
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.113 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
        "Accept-Language": "en-US,en;q=0.9",
        "Authorization": "bearer {}".format(GITHUB_TOKEN),
    }
    s = requests.session()
    s.keep_alive = False  # don't keep the session
    graphql_api = "https://api.github.com/graphql"
    try:
        r = requests.post(url=graphql_api, json={"query": GQL}, headers=headers)
        assert r.status_code == 200
        result = r.json()
        # If the error is rate limit, then sleep until X-RateLimit-Reset timestamp
        if "errors" in result:
            if result["errors"][0]["type"] == "RATE_LIMITED":
                reset_timestamp = int(r.headers["X-RateLimit-Reset"])
                sleep_time = reset_timestamp - time.time()
                print(
                    "Rate limited, sleeping for {} seconds until {}".format(
                        sleep_time, datetime.datetime.fromtimestamp(reset_timestamp)
                    )
                )
                time.sleep(sleep_time)
        assert "errors" not in result
        return result
    except Exception as e:
        if retries > 0:
            time.sleep(5)
            return get_graphql_data(GQL, retries - 1)
        raise e


def get_count(stars_fmt, date_fmt):
    gql_count = """query {
  search(query: "is:public stars:%s created:%s", type: REPOSITORY, first: 1) {
    repositoryCount
  }
}
  """ % (
        stars_fmt,
        date_fmt,
    )
    result = get_graphql_data(gql_count)
    return result["data"]["search"]["repositoryCount"]


def get_repo_data(stars_fmt, date_fmt):
    """
    Get 1000 repos by stars_fmt and date_fmt
    """
    # note: total repos on github is 62 million, with >0 stars is 13 million
    # Technically page size can go up to 100, but I see frequent 500 errors in testing
    default_page_size = 24
    make_pagination_str = lambda page_size, cursor: f"first: {page_size}" + (
        ', after: "{}"'.format(cursor) if cursor else ""
    )

    def do_query(cursor, page_size, retries=1):
        # Note: cannot list the number of collaborators on a repo with graphql, but can use graph api:
        # https://stackoverflow.com/a/57440667
        gql_stars = """query {
    search(query: "is:public stars:%s created:%s sort:stars", type: REPOSITORY, %s) {
      repositoryCount
      edges {
        __typename
        cursor
        node {
          __typename
          ... on Repository {
            id
            name
            nameWithOwner
            isFork
            forkCount
            licenseInfo {
              name
            }
            assignableUsers {
              totalCount
            }
            codeOfConduct {
              name
            }
            parent {
              nameWithOwner
            }
            forkingAllowed
            forkCount
            isArchived
            languages(first: 10, orderBy: {field:SIZE, direction: DESC}) {
              nodes {
                name
              }
              edges {
                size
              }
            }
            diskUsage
            stargazerCount
            watchers {
              totalCount
            }
            owner {
              login
            }
            pullRequests {
              totalCount
            }
            description
            pushedAt
            primaryLanguage {
              name
            }
            createdAt
            defaultBranchRef {
              target {
                ... on Commit {
                  history {
                    totalCount
                  }
                }
              }
            }
            pullRequests {
              totalCount
            }
            pushedAt
          }
        }
      }
    }
  }
      """
        try:
          result = get_graphql_data(
              gql_stars
              % (
                  stars_fmt,
                  date_fmt,
                  make_pagination_str(page_size, cursor),
              )
          )
        except Exception as e:
          # If we get an error, try again with small page size if we have retries left
          # Otherwise, return empty list
          if retries > 0:
            return do_query(cursor, page_size // 4, retries - 1)
          else:
            # Print a warning that we are skipping this query
            print(f"Too many errors, skipping query {stars_fmt} {date_fmt} cursor: {cursor} number: {page_size}")
            return [], None, page_size
        if len(result["data"]["search"]["edges"]) == 0:
            return [], None, page_size
        last_cursor = result["data"]["search"]["edges"][-1]["cursor"]
        return result["data"]["search"]["edges"], last_cursor, page_size

    new_result, last_cursor, page_size = do_query(None, default_page_size)
    final_result = new_result[:]
    while len(new_result) == page_size and len(final_result) < 1000:
        new_result, last_cursor, page_size = do_query(last_cursor, default_page_size)
        final_result += new_result
    return final_result


def deep_get(dictionary, keys, default=None):
    # From: https://stackoverflow.com/a/46890853/2288934
    # Usage: deep_get(my_dict, "a.b.c", default=None)
    return reduce(
        lambda d, key: d.get(key, default) if isinstance(d, dict) else default,
        keys.split("."),
        dictionary,
    )


def convert_to_json(result):
    """
    Convert the result of get_repo_data to a json-compatible dict
    """
    # The result from graphql is already json, but we can make it a little more compact
    json_result = {
        "owner": deep_get(result, "node.owner.login"),
        "name": deep_get(result, "node.name"),
        "stars": deep_get(result, "node.stargazerCount"),
        "forks": deep_get(result, "node.forkCount"),
        "watchers": deep_get(result, "node.watchers.totalCount"),
        "isFork": deep_get(result, "node.isFork"),
        "isArchived": deep_get(result, "node.isArchived"),
        "languages": [
            {"name": deep_get(name, "name"), "size": deep_get(size, "size")}
            for name, size in zip(
                deep_get(result, "node.languages.nodes"),
                deep_get(result, "node.languages.edges"),
            )
        ],
        "diskUsageKb": deep_get(result, "node.diskUsage"),
        "pullRequests": deep_get(result, "node.pullRequests.totalCount"),
        "description": deep_get(result, "node.description"),
        "primaryLanguage": deep_get(result, "node.primaryLanguage.name"),
        "createdAt": deep_get(result, "node.createdAt"),
        "pushedAt": deep_get(result, "node.pushedAt"),
        "defaultBranchCommitCount": deep_get(
            result, "node.defaultBranchRef.target.history.totalCount"
        ),
        "license": deep_get(result, "node.licenseInfo.name"),
        "assignableUserCount": deep_get(result, "node.assignableUsers.totalCount"),
        "codeOfConduct": deep_get(result, "node.codeOfConduct.name"),
        "forkingAllowed": deep_get(result, "node.forkingAllowed"),
        "nameWithOwner": deep_get(result, "node.nameWithOwner"),
        "parent": deep_get(result, "node.parent.nameWithOwner"),
    }

    return json_result


def bisect_stars_and_dates(star_start, star_end, date_start, date_end):
    """
    Bisect the space of stars and dates to find all regions with less than 1000
    Returns a list of [(star_fmt, date_fmt)] pairs
    star_fmt has the format star_start..star_end
    date_fmt has the format date_start..date_end, e.g. 2011-07-29..2011-07-30
    """
    final_regions = []
    missed = 0
    parse_date = lambda x: datetime.datetime.strptime(x, "%Y-%m-%d")
    format_date = lambda x: datetime.datetime.strftime(x, "%Y-%m-%d")
    # First we will bisect by star, if we get to 1 star and still more than 1000 repos, we will bisect by dates
    star_fmt = f"{star_start}..{star_end}"
    date_fmt = f"{format_date(date_start)}..{format_date(date_end)}"
    bisection_queue = [(star_fmt, date_fmt)]

    def do_bisection():
        # Note that bisection ranges are inclusive
        if star_end - star_start > 0:
            # Bisect stars
            star_mid = (star_start + star_end) // 2
            bisection_queue.append((f"{star_start}..{star_mid}", date_fmt))
            bisection_queue.append((f"{star_mid+1}..{star_end}", date_fmt))
        else:
            # Bisect dates, unless we are down to one day, then print a warning
            if date_end.date() == date_start.date():
                print(
                    f"WARNING: Could not find a region with less than 1000 repos for stars {star_fmt} dates {date_fmt}, size is {count} repos"
                )
                missed += count - 1000
                final_regions.append((star_fmt, date_fmt, count))
                return
            date_mid = date_start + (date_end - date_start) // 2
            bisection_queue.append(
                (
                    star_fmt,
                    f"{format_date(date_start)}..{format_date(date_mid)}",
                )
            )
            bisection_queue.append(
                (
                    star_fmt,
                    f"{format_date(date_mid+datetime.timedelta(days=1))}..{format_date(date_end)}",
                )
            )

    # Create a progress bar with tqdm to show the bisection queue and the regions found
    with tqdm(desc="Regions found /queue") as progress:
        while len(bisection_queue) > 0:
            progress.n = len(final_regions)
            progress.total = len(bisection_queue) + len(final_regions)
            progress.refresh()
            star_fmt, date_fmt = bisection_queue.pop(0)
            star_start, star_end = [int(x) for x in star_fmt.split("..")]
            date_start, date_end = [parse_date(x) for x in date_fmt.split("..")]
            count = get_count(star_fmt, date_fmt)
            if 0 < count <= 1000:
                final_regions.append((star_fmt, date_fmt, count))
            elif count == 0:
                # No repos in this region, skip
                continue
            else:
                do_bisection()
        # Make sure the progress bar shows 100% when we are done
        progress.n = progress.total
        progress.refresh()

    # Print warning about how many we will miss
    if missed > 0:
        print(
            f"WARNING: Missed {missed} repos, because of minimal regions with more than 1000 repos"
        )
    return final_regions


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--resume",
        help="Path to regions.pkl from a previous run",
        default=None,
    )
    args = parser.parse_args()

    if not args.resume:
        config = DEFAULT_CONFIG
        start_date = config["date_range"][0]
        end_date = config["date_range"][1]
        star_start = config["star_range"][0]
        star_end = config["star_range"][1]
        output_filename = get_output_filename(config)
        print(
            "Performing bisection on star date space from %s to %s"
            % (start_date.date(), end_date.date())
        )
        regions = bisect_stars_and_dates(star_start, star_end, start_date, end_date)
        # Pickle regions to a file for resume feature
        with open("regions.pkl", "wb") as f:
            pickle.dump({"regions": regions, "config": config}, f)
        # If we are not resuming, then we need to delete the output file if it exists
        if os.path.exists(output_filename):
            os.remove(output_filename)
        print(
            "Pickled regions to regions.pkl for resume feature, use --resume to continue if processing is interrupted"
        )
    else:
        print("Resuming from previous run")
        with open(args.resume, "rb") as f:
            previous_run = pickle.load(f)
            regions = previous_run["regions"]
            config = previous_run["config"]
        output_filename = get_output_filename(config)
        # If output file exists, then we need to remove the processed regions from the regions list
        # Remove the first n regions from the list, where n is the number of lines in the output file
        if os.path.exists(output_filename):
            with open(output_filename, "r") as f:
                line_count = sum(1 for _ in f)
                regions = regions[line_count:]

    print(f"Found {len(regions)} star date regions")
    total_repos = sum([count for (_, _, count) in regions])
    print(f"Total repositories: {total_repos}")
    processed_count = 0
    print(f"Writing output to {output_filename} (one json object per line)")
    with tqdm(desc="Processed /total", total=total_repos) as progress:
        for (star_fmt, date_fmt, _) in regions:
            results = get_repo_data(star_fmt, date_fmt)
            json_data = [convert_to_json(result) for result in results]
            processed_count += len(json_data)
            progress.n = processed_count
            progress.refresh()
            with open(output_filename, "a") as f:
                json.dump(json_data, f)
                f.write("\n")
    print(f"Processed {processed_count} repos, total {total_repos} repos")

    # Here at the very end we merge all of the json lines into a single array, then write it back out
    # This is done so that the output file is a valid json file
    print(f"Merging json lines into a single json array")
    with open(output_filename, "r") as f:
        json_data = [json.loads(line) for line in tqdm(f)]
    # Flatten the list of lists
    json_data = [item for sublist in json_data for item in sublist]
    with open(output_filename, "w") as f:
        json.dump(json_data, f)
    print(f"Output written to {output_filename}")


if __name__ == "__main__":
    main()
