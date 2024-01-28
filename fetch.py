#!/opt/homebrew/bin//python3.10
import concurrent.futures
from dataclasses import dataclass
import re
from typing import List, Optional, Any

import requests
from bs4 import BeautifulSoup


BLACKLISTED_ROLES = 'veileder sfo assistent barneveileder'.split()

PIC_FOLDER = "pics"


@dataclass
class Teacher:
    name: str
    img_url: str
    school: str
    role: Optional[str] = None
    school: Optional[str] = None
    img_path: Optional[str] = None
    predicted_age: Optional[int] = None
    email: Optional[str] = None
    phone_number: Optional[int] = None

def load_urls() -> List[tuple[str, List[str]]]:
    with open("URLS.txt", "r") as f:
        lines = f.read().splitlines()
    final = []
    stack = []
    current_school = lines[0][1:]
    for line in lines:
        if line.startswith("#"):
            final.append((current_school, stack))
            stack = []
            current_school = line[1:]
        else:
            stack.append(line)

    final.append((current_school, stack))
    return list(filter(lambda x: len(x[1]) > 0, final))


def download_image(teacher: Teacher) -> None:
    r = requests.get(teacher.img_url)
    n = teacher.name.replace(" ", "-")
    with open(f"{PIC_FOLDER}/{n}.jpg", "wb") as f:
        f.write(r.content)
        print(f"Downloaded {teacher.name}")


def download_images(e: List[Teacher]) -> None:
    with concurrent.futures.ThreadPoolExecutor() as executor:
        executor.map(download_image, e)


def format_img_url(img_path: str, school_url: str) -> str:
    u = school_url.split("/")
    u.pop()
    u.append(img_path)
    return "/".join(u)


def parse_teachers(url: str, school_name: str) -> List[Teacher]:
    teachers = []
    processes = []
    try:
        r = requests.get(url).text
    except:
        print(f"SKIPPED, {url}")
        return []

    soup = BeautifulSoup(r, "html.parser")

    with concurrent.futures.ThreadPoolExecutor() as executor:
        for tr in soup.find_all("tr"):
            processes.append(
                executor.submit(fetch_data_for_teacher, tr, url, school_name)
            )
        for process in concurrent.futures.as_completed(processes):
            if process.result() is not None:
                teachers.append(process.result())
    return teachers


def get_email(third_td: Any, url: str) -> Optional[str]:
    try:
        email_ids = third_td.find_all("a", {"class": "m-sendEmailToUser"})
        image_post_url = url.split("?")[0] + "?show=ajax&module=users"
        email_type = "arb"
        for a in email_ids:
            if "priv" in a["data-emailtype"]:
                email_type = "priv"
                break

        headers = {
            "do": "getMailAddress",
            "emailID": str(a["data-id"]),
            "emailType": email_type,
        }
        response = requests.post(
            image_post_url, data=headers, cookies={
                # only works when you have a random, arbitrary cookie.
                # good job, moava!
                "dhfd": "dhfd"})
        email = response.text
    except:
        email = None
    return email


def get_phone_number(third_td: Any) -> Optional[int]:
    try:
        text = third_td.text
        match = re.search(r"(Tlf\. arb\.:|Mobil:)\s*([\d\s]+)", text)
        phone_number = int(match.group(2).replace(" ", "")) if match else None
    except:
        phone_number = None
    return phone_number


def get_role(second_td: Any) -> Optional[str]:
    try:
        role = (
            second_td.find("br")
            .next_sibling.strip()
            .replace("\n", "")
            .replace("\t", "")
        )
    except:
        role = None
    return role


def fetch_data_for_teacher(
    teacher_tr_tag: Any, url: str, school_name: str
) -> Optional[Teacher]:
    tds = teacher_tr_tag.find_all("td")
    img_tag = tds[0].find("img")
    if img_tag is None:
        return

    try:
        name = tds[1].find("strong").text
    except:
        return
    img_url = format_img_url(img_tag["src"], url)
    if img_url == "":
        return

    # email
    try:
        email = get_email(tds[2], url)
    except:
        email = None

    # phone number
    try:
        phone_number = get_phone_number(tds[2])
    except:
        phone_number = None

    # role
    try:
        role = get_role(tds[1])
    except:
        role = None

    if role is not None:
        if any(b_role in role.lower() for b_role in BLACKLISTED_ROLES):
            return

    ret = Teacher(
        name=name.replace("  ", " "),
        img_url=img_url,
        role=role,
        school=school_name,
        email=email,
        phone_number=phone_number,
    )
    print(ret)
    return ret


def fetch_data_of_all_schools() -> List[Teacher]:
    total = []
    for school, urls in load_urls():
        print(school)
        for url in urls:
            total.extend(parse_teachers(url, school))

    return total


def remove_duplicates(teachers: List[Teacher]) -> List[Teacher]:
    seen = set()
    return [
        t
        for t in teachers
        if repr(t) not in seen and not seen.add(repr(t))
    ]


def main() -> None:
    teachers = fetch_data_of_all_schools()
    teachers = remove_duplicates(teachers)
    print(len(teachers))

    with open("result.json", "wt") as f:
        f.write(str([{k: v for k, v in t.__dict__.items() if v is not None}
                for t in teachers]).replace("'", '"'))

    # Only if you want to download the images
    download_images(teachers)


if __name__ == "__main__":
    main()
