from dataclasses import dataclass

import requests


@dataclass
class User:
    name: str
    organizations: list[str]


@dataclass
class Commit:
    message: str
    user: User
    additions: int
    deletions: int


def call_with_query(query, token):
    url = 'https://api.github.com/graphql'
    r = requests.post(url, json={'query': query}, headers={'Authorization': f'Bearer {token}'})
    return r.json()


def get_tag_commit_date(token, repository, tag):
    owner, name = repository.split('/')
    query = f"""
    query GetTagCommit {{
        repository(owner: "{owner}", name: "{name}"){{
            object(expression: "{tag}") {{
                ... on Commit {{
                    oid
                    message
                    committedDate
                    author {{
                        user {{
                            login
                        }}
                    }}
                }}
            }}
        }}
    }}
    """

    response = call_with_query(query, token)

    try:
        repository = response['data']['repository']['object']

        if repository is None:
            if 'errors' in response:
                raise ValueError(response['errors'][0]['message'])
            raise ValueError('Invalid tag. Does this tag exist?')

        committed_date = repository['committedDate']
    except (KeyError, TypeError):
        raise ValueError('Invalid token. Does your token have the valid permissions?')

    return committed_date


def get_commits(token, repository, branch, since):
    owner, name = repository.split('/')

    def get_page_result(next_page=''):
        query = f"""
        query GetCommits {{
            repository(owner: "{owner}", name: "{name}"){{
                nameWithOwner
                object(expression: "{branch}") {{
                    ... on Commit {{
                        oid
                        history(first: 100, since: "{since}"{next_page}) {{
                            nodes {{
                                message
                                deletions
                                additions
                                author {{
                                    user {{
                                        login
                                        organizations(first: 100) {{
                                            nodes {{
                                                name
                                            }}
                                        }}
                                    }}
                                }}
                            }}
                            pageInfo {{
                                endCursor
                                hasNextPage
                            }}
                        }}
                    }}
                }}
            }}
        }}
        """
        result = call_with_query(query, token)

        if 'data' not in result:
            raise ValueError(result['errors'][0]['message'])

        if result['data']['repository']['object'] is None:
            raise ValueError("Either the tag or the branch were incorrect.")

        nodes = result['data']['repository']['object']['history']['nodes']
        cursor = result['data']['repository']['object']['history']['pageInfo']['endCursor']
        return nodes, cursor

    nodes, cursor = get_page_result()

    while cursor is not None:
        _nodes, cursor = get_page_result(f' after:"{cursor}"')
        nodes.extend(_nodes)


    commits = []
    for node in nodes:
        if node['author']['user'] is None:
            commits.append(Commit(
                message=node['message'].split('\n')[0],
                user=User(name='<NOT FOUND>', organizations=[]),
                additions=node.get('additions'),
                deletions=node.get('deletions')
            ))
        else:
            commits.append(Commit(
                message=node['message'].split('\n')[0],
                user=User(name=node['author']['user']['login'], organizations=[n['name'] for n in node['author']['user']['organizations']['nodes']]),
                additions=node.get('additions'),
                deletions=node.get('deletions')
            ))

    return commits
