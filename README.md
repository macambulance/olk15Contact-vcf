# olk15_to_vcf

Converts contact files saved by **Outlook for Mac** (`.olk15Contact`) into standard **vCard** (`.vcf`) files that can be imported into Apple Contacts, Google Contacts, Outlook and most other address book apps.

The `.olk15Contact` format is proprietary and undocumented. The field mapping used here was worked out by inspecting sample files, so see [Limitations](#limitations).

## Requirements

- Python 3.7 or newer (works with the Python 3.9 that ships with macOS)
- No third-party packages

## Usage

```
python3 olk15_to_vcf.py INPUT_FOLDER [OUTPUT_FOLDER] [--combined] [--debug]
```

| Argument | Description |
| --- | --- |
| `INPUT_FOLDER` | Folder containing `.olk15Contact` files. Subfolders are searched too. |
| `OUTPUT_FOLDER` | Where the `.vcf` files are written. Defaults to a `vcf_output` folder inside the input folder. Created if it doesn't exist. |
| `--combined` | Also write a single `all_contacts.vcf` containing every contact. |
| `--debug` | Print the raw fields found in each file. Useful for troubleshooting. |

### Example

```
python3 olk15_to_vcf.py ~/Downloads/contacts ~/Downloads/contacts/vcf --combined
```

When it finishes it prints how many vCards were written, and lists any files that need a look (no name, no email address, or unreadable).

## Output

- One `.vcf` file per contact, named `First_Last.vcf`. If two contacts share a name, later ones become `First_Last_2.vcf`, `First_Last_3.vcf` and so on.
- Contacts with no first name or surname are named after their company, or failing that the original file name.
- vCard version 3.0, UTF-8, with CRLF line endings and long lines folded as the spec requires.

## Fields extracted

| vCard field | Outlook field |
| --- | --- |
| `N` / `FN` | First name, surname |
| `EMAIL` | Up to three email addresses (the first is marked preferred) |
| `ORG` | Company |
| `TITLE` | Job title |
| `TEL` | Up to three phone numbers |
| `ADR` | Street, city, state, postcode, country (work address) |
| `URL` | Website |
| `NOTE` | Notes, with the HTML stripped to plain text |

Empty fields are left out. If a contact has no name, `FN` falls back to the company, then the email address.

## Limitations

- **Phone types are unconfirmed.** The first phone number is tagged `WORK`. The others are plain `TEL` entries, because it couldn't be confirmed which slot is fax, mobile and so on.
- **Only text fields are read.** Photos, birthdays, categories, and other non-text properties are not extracted.
- **Data is copied as stored.** If a contact has a company name in the first name and surname fields, or capitalisation is inconsistent, the vCard will reflect that.
- **Contacts without an email address** are still converted, but are listed in the end-of-run summary so you can check them.
- Based on sample files from Outlook for Mac. Files from other versions may use different field IDs.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `Found 0 .olk15Contact file(s)` | Check the input path. The extension match is case-insensitive, and subfolders are searched. |
| `check: ... could not parse` | The file doesn't match the expected structure. Run with `--debug` and inspect it. |
| `TypeError: write_text() got an unexpected keyword argument 'newline'` | You have an old copy of the script written for Python 3.10+. Use the current version. |
| A name or phone number ends up in the wrong field | Run with `--debug` and check the field IDs in `olk15_to_vcf.py` (the `FIELD_*` constants near the top). |
