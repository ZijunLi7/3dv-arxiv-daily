import os
import re
import json
import arxiv
import yaml
import logging
import argparse
import datetime
import requests

logging.basicConfig(format='[%(asctime)s %(levelname)s] %(message)s',
                    datefmt='%m/%d/%Y %H:%M:%S',
                    level=logging.INFO)

# Removed base_url and github_url since code functionality is disabled
arxiv_url = "http://arxiv.org/"

EXCAPE = '\"'
QUOTA = '' # NO-USE
OR = ' OR ' # TODO
AND = ' AND '
ANDNOT = ' ANDNOT '
LEFT = '('
RIGHT = ')'

def key_connecter(key_list:list) -> str:
    ret = ''
    for idx in range(0,len(key_list)):
        words = key_list[idx]
        if ':' in words:
            prefix, words = words.split(':')
            ret += prefix + ':'
        if len(words.split()) > 1:
            ret += (EXCAPE + words + EXCAPE)
        else:
            ret += (QUOTA + words + QUOTA)
        if idx != len(key_list) - 1:
            ret += OR
    return ret

def load_config(config_file:str) -> dict:
    '''
    config_file: input config file path
    return: a dict of configuration
    '''
    # make filters pretty
    def pretty_filters(**config) -> dict:
        keywords = dict()
        def parse_filters(dicts:dict):
            ret = ''
            if 'filters' in dicts.keys():
                ret += LEFT + key_connecter(dicts['filters']) + RIGHT
                dicts.pop('filters')
            for k,v in dicts.items():
                if k != 'invert':
                    ret += AND if len(ret) > 0 else ''
                    ret += LEFT + key_connecter(v) + RIGHT
            if 'invert' in dicts.keys():
                ret += ANDNOT + LEFT + key_connecter(dicts['invert']) + RIGHT
            return ret

        for k,v in config['keywords'].items():
            keywords[k] = parse_filters(v)
        return keywords
    with open(config_file,'r') as f:
        config = yaml.load(f,Loader=yaml.FullLoader)
        config['kv'] = pretty_filters(**config)
        logging.info(f'config = {config}')
    return config

def get_authors(authors, first_author = False):
    output = str()
    if first_author == False:
        output = ", ".join(str(author) for author in authors)
    else:
        output = authors[0]
    return output
def sort_papers(papers):
    output = dict()
    keys = list(papers.keys())
    keys.sort(reverse=True)
    for key in keys:
        output[key] = papers[key]
    return output
import requests

# Removed get_code_link function since code functionality is disabled

def get_daily_papers(topic,query="slam", max_results=2):
    """
    @param topic: str
    @param query: str
    @return paper_with_code: dict
    """
    # output
    content = dict()
    content_to_web = dict()
    search_engine = arxiv.Search(
        query = query,
        max_results = max_results,
        sort_by = arxiv.SortCriterion.SubmittedDate
    )

    for result in search_engine.results():

        paper_id            = result.get_short_id()
        paper_title         = result.title
        paper_url           = result.entry_id
        paper_abstract      = result.summary.replace("\n"," ")
        paper_authors       = get_authors(result.authors)
        paper_first_author  = get_authors(result.authors,first_author = True)
        primary_category    = result.primary_category
        publish_time        = result.published.date()
        update_time         = result.updated.date()
        comments            = result.comment

        logging.info(f"Time = {update_time} title = {paper_title} author = {paper_first_author}")

        # eg: 2108.09112v1 -> 2108.09112
        ver_pos = paper_id.find('v')
        if ver_pos == -1:
            paper_key = paper_id
        else:
            paper_key = paper_id[0:ver_pos]
        paper_url = arxiv_url + 'abs/' + paper_key

        # Code functionality disabled - only show paper info without code links
        content[paper_key] = "|**{}**|**{}**|{} et.al.|[{}]({})|N/A|\n".format(
               update_time,paper_title,paper_first_author,paper_key,paper_url)
        content_to_web[paper_key] = "- {}, **{}**, {} et.al., Paper: [{}]({})".format(
               update_time,paper_title,paper_first_author,paper_url,paper_url)

        # TODO: select useful comments
        comments = None
        if comments != None:
            content_to_web[paper_key] += f", {comments}\n"
        else:
            content_to_web[paper_key] += f"\n"

    data = {topic:content}
    data_web = {topic:content_to_web}
    return data,data_web

def remove_old_papers(json_data, months=2):
    """
    Remove papers older than `months` months from json_data.
    Also returns the (min_date, max_date) range of remaining papers.
    @param json_data: dict  {keyword: {paper_id: content_str}}
    @param months: int, papers older than this many months will be removed
    @return: (cleaned json_data, min_date, max_date)
    """
    from dateutil.relativedelta import relativedelta
    cutoff_date = datetime.date.today() - relativedelta(months=months)
    date_pattern = re.compile(r'\|\*\*(\d{4}-\d{2}-\d{2})\*\*\|')
    all_dates = []
    for keyword in list(json_data.keys()):
        papers = json_data[keyword]
        to_remove = []
        for paper_id, content in papers.items():
            match = date_pattern.search(str(content))
            if match:
                paper_date = datetime.datetime.strptime(match.group(1), '%Y-%m-%d').date()
                if paper_date < cutoff_date:
                    to_remove.append(paper_id)
                else:
                    all_dates.append(paper_date)
            else:
                # Cannot parse date, keep the paper
                all_dates.append(datetime.date.today())
        for pid in to_remove:
            del papers[pid]
            logging.info(f'Removed old paper: {pid}')
    min_date = min(all_dates) if all_dates else datetime.date.today()
    max_date = max(all_dates) if all_dates else datetime.date.today()
    return json_data, min_date, max_date


def update_paper_links(filename):
    '''
    weekly update paper links in json file
    Note: Code functionality is disabled, so this function now only maintains existing data structure
    '''
    def parse_arxiv_string(s):
        parts = s.split("|")
        date = parts[1].strip()
        title = parts[2].strip()
        authors = parts[3].strip()
        arxiv_id = parts[4].strip()
        code = parts[5].strip()
        arxiv_id = re.sub(r'v\d+', '', arxiv_id)
        return date,title,authors,arxiv_id,code

    with open(filename,"r") as f:
        content = f.read()
        if not content:
            m = {}
        else:
            m = json.loads(content)

        json_data = m.copy()

        for keywords,v in json_data.items():
            logging.info(f'keywords = {keywords}')
            for paper_id,contents in v.items():
                contents = str(contents)

                update_time, paper_title, paper_first_author, paper_url, code_url = parse_arxiv_string(contents)

                # Code functionality disabled - maintain N/A for code links
                contents = "|{}|{}|{}|{}|N/A|\n".format(update_time,paper_title,paper_first_author,paper_url)
                json_data[keywords][paper_id] = str(contents)
                logging.info(f'paper_id = {paper_id}, contents = {contents}')

        # dump to json file
        with open(filename,"w") as f:
            json.dump(json_data,f)

def update_json_file(filename,data_dict):
    '''
    daily update json file using data_dict
    '''
    with open(filename,"r") as f:
        content = f.read()
        if not content:
            m = {}
        else:
            m = json.loads(content)

    json_data = m.copy()

    # update papers in each keywords
    for data in data_dict:
        for keyword in data.keys():
            papers = data[keyword]

            if keyword in json_data.keys():
                json_data[keyword].update(papers)
            else:
                json_data[keyword] = papers

    with open(filename,"w") as f:
        json.dump(json_data,f)

def json_to_md(filename,md_filename,
               task = '',
               to_web = False,
               use_title = True,
               use_tc = True,
               show_badge = True,
               use_b2t = True,
               date_range = None):
    """
    @param filename: str
    @param md_filename: str
    @return None
    """
    def pretty_math(s:str) -> str:
        ret = ''
        match = re.search(r"\$.*\$", s)
        if match == None:
            return s
        math_start,math_end = match.span()
        space_trail = space_leading = ''
        if s[:math_start][-1] != ' ' and '*' != s[:math_start][-1]: space_trail = ' '
        if s[math_end:][0] != ' ' and '*' != s[math_end:][0]: space_leading = ' '
        ret += s[:math_start]
        ret += f'{space_trail}${match.group()[1:-1].strip()}${space_leading}'
        ret += s[math_end:]
        return ret

    DateNow = datetime.date.today()
    DateNow = str(DateNow)
    DateNow = DateNow.replace('-','.')

    if date_range is not None:
        min_date, max_date = date_range
        date_display = "Select paper in {} - {}".format(
            str(min_date).replace('-','.'), str(max_date).replace('-','.'))
    else:
        date_display = "Select paper in " + DateNow

    with open(filename,"r") as f:
        content = f.read()
        if not content:
            data = {}
        else:
            data = json.loads(content)

    # clean README.md if daily already exist else create it
    with open(md_filename,"w+") as f:
        pass

    # write data into README.md
    with open(md_filename,"a+") as f:

        if (use_title == True) and (to_web == True):
            f.write("---\n" + "layout: default\n" + "---\n\n")

        # if show_badge == True:
        #     f.write(f"[![Contributors][contributors-shield]][contributors-url]\n")
        #     f.write(f"[![Forks][forks-shield]][forks-url]\n")
        #     f.write(f"[![Stargazers][stars-shield]][stars-url]\n")
        #     f.write(f"[![Issues][issues-shield]][issues-url]\n\n")

        if use_title == True:
            #f.write(("<p align="center"><h1 align="center"><br><ins>CV-ARXIV-DAILY"
            #         "</ins><br>Automatically Update CV Papers Daily</h1></p>\n"))
            f.write("## " + date_display + "\n")
        else:
            f.write("> " + date_display + "\n")

        #Add: table of contents
        if use_tc == True:
            f.write("<details>\n")
            f.write("  <summary>Table of Contents</summary>\n")
            f.write("  <ol>\n")
            for keyword in data.keys():
                day_content = data[keyword]
                if not day_content:
                    continue
                kw = keyword.replace(' ','-')
                f.write(f"    <li><a href=#{kw.lower()}>{keyword}</a></li>\n")
            f.write("  </ol>\n")
            f.write("</details>\n\n")

        for keyword in data.keys():
            day_content = data[keyword]
            if not day_content:
                continue
            # the head of each part
            f.write(f"## {keyword}\n\n")

            if use_title == True :
                if to_web == False:
                    f.write("|Publish Date|Title|Authors|PDF|Code|\n" + "|---|---|---|---|---|\n")
                else:
                    f.write("| Publish Date | Title | Authors | PDF | Code |\n")
                    f.write("|:---------|:-----------------------|:---------|:------|:------|\n")

            # sort papers by date
            day_content = sort_papers(day_content)

            for _,v in day_content.items():
                if v is not None:
                    f.write(pretty_math(v)) # make latex pretty

            f.write(f"\n")

            #Add: back to top
            if use_b2t:
                top_info = f"#{date_display}"
                top_info = top_info.replace(' ','-').replace('.','')
                f.write(f"<p align=right>(<a href={top_info.lower()}>back to top</a>)</p>\n\n")

        if show_badge == True:
            # we don't like long string, break it!
            f.write((f"[contributors-shield]: https://img.shields.io/github/"
                     f"contributors/Vincentqyw/cv-arxiv-daily.svg?style=for-the-badge\n"))
            f.write((f"[contributors-url]: https://github.com/Vincentqyw/"
                     f"cv-arxiv-daily/graphs/contributors\n"))
            f.write((f"[forks-shield]: https://img.shields.io/github/forks/Vincentqyw/"
                     f"cv-arxiv-daily.svg?style=for-the-badge\n"))
            f.write((f"[forks-url]: https://github.com/Vincentqyw/"
                     f"cv-arxiv-daily/network/members\n"))
            f.write((f"[stars-shield]: https://img.shields.io/github/stars/Vincentqyw/"
                     f"cv-arxiv-daily.svg?style=for-the-badge\n"))
            f.write((f"[stars-url]: https://github.com/Vincentqyw/"
                     f"cv-arxiv-daily/stargazers\n"))
            f.write((f"[issues-shield]: https://img.shields.io/github/issues/Vincentqyw/"
                     f"cv-arxiv-daily.svg?style=for-the-badge\n"))
            f.write((f"[issues-url]: https://github.com/Vincentqyw/"
                     f"cv-arxiv-daily/issues\n\n"))

    logging.info(f"{task} finished")

def keyword_to_slug(keyword):
    """Convert keyword name to URL-friendly slug.
    e.g. '3D Reconstruction' -> '3d_reconstruction'
         'NeRF & Gaussian' -> 'nerf_gaussian'
    """
    slug = keyword.lower()
    slug = re.sub(r'[&]+', '', slug)
    slug = re.sub(r'[^a-z0-9]+', '_', slug)
    slug = slug.strip('_')
    return slug

def generate_subpages(json_file, docs_dir, date_range=None, show_badge=False):
    """
    Generate individual sub-pages under docs/ for each keyword topic.
    Each sub-page is at docs/<slug>/index.md and contains a navigation bar.
    Also generates a landing page at docs/index.md.
    """
    def pretty_math(s:str) -> str:
        ret = ''
        match = re.search(r"\$.*\$", s)
        if match == None:
            return s
        math_start,math_end = match.span()
        space_trail = space_leading = ''
        if s[:math_start][-1] != ' ' and '*' != s[:math_start][-1]: space_trail = ' '
        if s[math_end:][0] != ' ' and '*' != s[math_end:][0]: space_leading = ' '
        ret += s[:math_start]
        ret += f'{space_trail}${match.group()[1:-1].strip()}${space_leading}'
        ret += s[math_end:]
        return ret

    with open(json_file, "r") as f:
        content = f.read()
        data = json.loads(content) if content else {}

    if not data:
        logging.info("No data for subpages")
        return []

    # Build date display string
    DateNow = str(datetime.date.today()).replace('-', '.')
    if date_range is not None:
        min_date, max_date = date_range
        date_display = "Select paper in {} - {}".format(
            str(min_date).replace('-', '.'), str(max_date).replace('-', '.'))
    else:
        date_display = "Select paper in " + DateNow

    # Build slug mapping for all keywords
    all_keywords = list(data.keys())
    slug_map = {kw: keyword_to_slug(kw) for kw in all_keywords}

    # Build navigation bar HTML
    def make_nav_bar(current_keyword):
        nav = '<div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px;">\n'
        # Link back to main page
        nav += '  <a href="../" style="padding:4px 12px;border-radius:4px;background:#e0e0e0;color:#333;text-decoration:none;">Home</a>\n'
        for kw in all_keywords:
            slug = slug_map[kw]
            if kw == current_keyword:
                nav += f'  <a href="../{slug}/" style="padding:4px 12px;border-radius:4px;background:#0366d6;color:#fff;text-decoration:none;font-weight:bold;">{kw}</a>\n'
            else:
                nav += f'  <a href="../{slug}/" style="padding:4px 12px;border-radius:4px;background:#e0e0e0;color:#333;text-decoration:none;">{kw}</a>\n'
        nav += '</div>\n\n'
        return nav

    generated_files = []

    # Generate sub-page for each keyword
    for keyword in all_keywords:
        day_content = data[keyword]
        if not day_content:
            continue

        slug = slug_map[keyword]
        subpage_dir = os.path.join(docs_dir, slug)
        os.makedirs(subpage_dir, exist_ok=True)
        md_path = os.path.join(subpage_dir, 'index.md')

        with open(md_path, 'w') as f:
            # Jekyll front matter
            f.write("---\n")
            f.write("layout: default\n")
            f.write(f"title: {keyword}\n")
            f.write("---\n\n")

            # Navigation bar
            f.write(make_nav_bar(keyword))

            # Title
            f.write(f"## {keyword}\n\n")
            f.write(f"_{date_display}_\n\n")

            # Table
            f.write("| Publish Date | Title | Authors | PDF | Code |\n")
            f.write("|:---------|:-----------------------|:---------|:------|:------|\n")

            # Sort papers by date
            sorted_content = sort_papers(day_content)
            for _, v in sorted_content.items():
                if v is not None:
                    f.write(pretty_math(v))

            f.write("\n")

        generated_files.append(md_path)
        logging.info(f"Generated subpage: {md_path}")

    # Generate landing page at docs/index.md
    index_path = os.path.join(docs_dir, 'index.md')
    with open(index_path, 'w') as f:
        f.write("---\n")
        f.write("layout: default\n")
        f.write("---\n\n")

        # Navigation bar (Home highlighted)
        f.write('<div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px;">\n')
        f.write('  <a href="./" style="padding:4px 12px;border-radius:4px;background:#0366d6;color:#fff;text-decoration:none;font-weight:bold;">Home</a>\n')
        for kw in all_keywords:
            if not data[kw]:
                continue
            slug = slug_map[kw]
            f.write(f'  <a href="{slug}/" style="padding:4px 12px;border-radius:4px;background:#e0e0e0;color:#333;text-decoration:none;">{kw}</a>\n')
        f.write('</div>\n\n')

        f.write(f"## 3DV Arxiv Daily\n\n")
        f.write(f"_{date_display}_\n\n")
        f.write("### Topics\n\n")
        f.write('<div style="display:flex;flex-wrap:wrap;gap:12px;margin-bottom:16px;">\n')
        for kw in all_keywords:
            if not data[kw]:
                continue
            slug = slug_map[kw]
            paper_count = len(data[kw])
            f.write(f'  <a href="{slug}/" style="padding:8px 16px;border-radius:6px;background:#0366d6;color:#fff;text-decoration:none;font-size:1.1em;">{kw} ({paper_count})</a>\n')
        f.write('</div>\n')

    generated_files.append(index_path)
    logging.info("Generated landing page: " + index_path)

    return generated_files

def demo(**config):
    # TODO: use config
    data_collector = []
    data_collector_web= []

    keywords = config['kv']
    max_results = config['max_results']
    publish_readme = config['publish_readme']
    publish_gitpage = config['publish_gitpage']
    publish_wechat = config['publish_wechat']
    show_badge = config['show_badge']

    b_update = config['update_paper_links']
    logging.info(f'Update Paper Link = {b_update}')
    if config['update_paper_links'] == False:
        logging.info(f"GET daily papers begin")
        for topic, keyword in keywords.items():
            logging.info(f"Keyword: {topic}")
            data, data_web = get_daily_papers(topic, query = keyword,
                                            max_results = max_results)
            data_collector.append(data)
            data_collector_web.append(data_web)
            print("\n")
        logging.info(f"GET daily papers end")

    # 1. update README.md file
    if publish_readme:
        json_file = config['json_readme_path']
        md_file   = config['md_readme_path']
        # update paper links
        if config['update_paper_links']:
            update_paper_links(json_file)
        else:
            # update json data
            update_json_file(json_file,data_collector)
        # remove papers older than 6 months
        with open(json_file,"r") as f:
            content = f.read()
            json_data = json.loads(content) if content else {}
        json_data, min_date, max_date = remove_old_papers(json_data)
        with open(json_file,"w") as f:
            json.dump(json_data, f)
        # json data to markdown
        json_to_md(json_file,md_file, task ='Update Readme', \
            show_badge = show_badge, date_range=(min_date, max_date))

    # 2. update docs/index.md file (to gitpage) + generate sub-pages
    if publish_gitpage:
        json_file = config['json_gitpage_path']
        md_file   = config['md_gitpage_path']
        # TODO: duplicated update paper links!!!
        if config['update_paper_links']:
            update_paper_links(json_file)
        else:
            update_json_file(json_file,data_collector)
        # remove papers older than 6 months
        with open(json_file,"r") as f:
            content = f.read()
            json_data = json.loads(content) if content else {}
        json_data, min_date, max_date = remove_old_papers(json_data)
        with open(json_file,"w") as f:
            json.dump(json_data, f)
        # Generate per-topic sub-pages + landing page
        docs_dir = os.path.dirname(json_file)  # 'docs' directory
        generate_subpages(json_file, docs_dir,
                          date_range=(min_date, max_date),
                          show_badge=show_badge)

    # 3. Update docs/wechat.md file
    if publish_wechat:
        json_file = config['json_wechat_path']
        md_file   = config['md_wechat_path']
        # TODO: duplicated update paper links!!!
        if config['update_paper_links']:
            update_paper_links(json_file)
        else:
            update_json_file(json_file, data_collector_web)
        # remove papers older than 6 months
        with open(json_file,"r") as f:
            content = f.read()
            json_data = json.loads(content) if content else {}
        json_data, min_date, max_date = remove_old_papers(json_data)
        with open(json_file,"w") as f:
            json.dump(json_data, f)
        json_to_md(json_file, md_file, task ='Update Wechat', \
            to_web=False, use_title= False, show_badge = show_badge, \
            date_range=(min_date, max_date))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--config_path',type=str, default='config.yaml',
                            help='configuration file path')
    parser.add_argument('--update_paper_links', default=False,
                        action="store_true",help='whether to update paper links etc.')
    args = parser.parse_args()
    config = load_config(args.config_path)
    config = {**config, 'update_paper_links':args.update_paper_links}
    demo(**config)
