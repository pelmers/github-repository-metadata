# 3 Million Github Repositories

## Introduction
As an intermediate result of my master's project, I am sharing a dataset of all public Github
repositories with at least 5 stars.
It's available [here on Kaggle](https://www.kaggle.com/datasets/pelmers/github-repository-metadata-with-5-stars).

This dataset is obtained from the Github API and contains only public repository-level metadata.
It may be useful for anyone interested in studying the Github ecosystem.
Please see the sample exploration notebook for some examples of what you can do!

## Dataset
The dataset is a JSON array of objects with the following fields:
- `name`: the name of the repository
- `description`: the description of the repository
- `owner`: the Github username of the owner of the repository
- `stars`: the number of stars the repository has
- `forks`: the number of forks the repository has
- `watchers`: the number of watchers the repository has
- `createdAt`: the date the repository was created
- `pushedAt`: the date the repository was last pushed to
- `license`: the name of the license of the repository
- `codeOfConduct`: the name of the code of conduct of the repository
- `isFork`: whether the repository is a fork
- `parent`: the name of the parent repository if the repository is a fork
- `forkingAllowed`: whether forking is allowed
- `isArchived`: whether the repository is archived
- `diskUsageKb`: the size of the repository in kilobytes
- `assignableUsersCount`: the number of assignable users
- `defaultBranchCommitCount`: the number of commits on the default branch
- `pullRequests`: the total number of pull requests
- `primaryLanguage`: the primary language of the repository
- `languages`: the first 10 languages of the repository, a list of objects with the fields `name` and `size` (ordered by size)
- `topics`: the first 10 topics of the repository, a list of objects with the fields `name` and `stars`
- `topicCount`: the number of topics the repository has
- `languageCount`: the number of languages the repository has
- `issues`: the total number of issues

## Example entry
```json
{
  "owner": "pelmers",
  "name": "text-rewriter",
  "stars": 13,
  "forks": 5,
  "watchers": 4,
  "isFork": false,
  "isArchived": false,
  "languages": [ { "name": "JavaScript", "size": 21769 }, { "name": "HTML", "size": 2096 }, { "name": "CSS", "size": 2081 } ],
  "languageCount": 3,
  "topics": [ { "name": "chrome-extension", "stars": 43211 } ],
  "topicCount": 1,
  "diskUsageKb": 75,
  "pullRequests": 4,
  "issues": 12,
  "description": "Webextension to rewrite phrases in pages",
  "primaryLanguage": "JavaScript",
  "createdAt": "2015-03-14T22:35:11Z",
  "pushedAt": "2022-02-11T14:26:00Z",
  "defaultBranchCommitCount": 54,
  "license": null,
  "assignableUserCount": 1,
  "codeOfConduct": null,
  "forkingAllowed": true,
  "nameWithOwner": "pelmers/text-rewriter",
  "parent": null
}
```

## Details
This repository contains two things:
1. A script to create the dataset, `get_all_github_repos.py`
2. An example notebook to show how to use the dataset, `explore_github_all_repos.ipynb`
For more detailed background info, you can read [my blog post](https://pelmers.com/all-of-the-github/).

The example notebook is also [available on Kaggle](https://www.kaggle.com/code/pelmers/explore-github-repository-metadata).

## Usage
The script `get_all_github_repos.py` creates the dataset. To use it:
1. Save a [Github Personal Access Token (classic)](https://github.com/settings/tokens) in a file called `github_token`.
2. Edit `DEFAULT_CONFIG` at the top of the file to adjust the star and date windows.
3. `python get_all_github_repos.py`
4. Note: the script may take several days to run. It will first bisect the star and date space
into regions to outwit the [Github API 1000 result limit](https://github.com/PyGithub/PyGithub/issues/1072). It saves this region information in `regions.pkl`
5. If the script ends before completion, you can therefore resume with `python get_all_github_repos.py --resume regions.pkl`

## Citing
This dataset is part of my master's thesis. You can cite it as below.
```
@mastersthesis{elmerscode,
  title        = {Code and Comment Consistency Classification with Large Language Models},
  author       = {Peter Elmers},
  year         = 2023,
  month        = {October},
  address      = {Eindhoven, Netherlands},
  note         = {Available at \url{https://research.tue.nl/files/319363283/Elmers_P.pdf}},
  school       = {Eindhoven University of Technology},
  type         = {Master's thesis}
}
```


## Terms
The [Github API Terms of Service](https://docs.github.com/en/site-policy/github-terms/github-terms-of-service#h-api-terms) apply.
> You may not use this dataset for spamming purposes, including for the purposes of selling GitHub users' personal information, such as to recruiters, headhunters, and job boards.
