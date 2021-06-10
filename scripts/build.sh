#!/usr/bin/env bash
# This is needed to force shellcheck to actually run, and bash and zsh are
# typically close enough that it shouldn't cause a problem.
# vim: set noexpandtab sw=2 ts=2 sts=2 nospell:

set -eux

if [ -x /usr/bin/uname ]; then
	UNAME_BIN="/usr/bin/uname"
elif [ -x /bin/uname ]; then
	UNAME_BIN="/bin/uname"
else
	printf 'Could not find uname\n' >&2
	return 1
fi
PLATFORM="$("${UNAME_BIN}" | /usr/bin/tr '[:upper:]' '[:lower:]')"

# Find the repo root dir
cd "$(/usr/bin/dirname "${0}")"
while [ "${PWD}" != "/" ]; do
	if [ -d "${PWD}/.git" ] || [ -d "${PWD}/.hg" ]; then
		break
	fi
	cd ../
done
if [ "${PWD}" = "/" ]; then
	printf 'Could not find repository starting from %s\n' "$(/usr/bin/dirname "${0}")" >&2
	return 1
fi

# Creates a POT file suitable for translators to use for generating localization
# translations. The output file is always './translations/messages.pot'.
make_pot() {
	if [ ! -d "./translations" ]; then
		mkdir ./translations
	fi

	# We explicitly do not want to quote the subcommand here since it prints
	# each file surrounded by quotes already.
	XGETTEXT_BIN="$(command -v xgettext)"
	# shellcheck disable=SC2046
	"${XGETTEXT_BIN}" -o ./translations/messages.pot --no-wrap \
		--copyright-holder="Joel Goguen" --package-name="calibre-kobo-driver" \
		$(/usr/bin/find . -type f -name '*.py' -not \( -name 'pygettext.py' -or -name 'test_*.py' -or -path '*/calibre-*' \))
}

# Equivalent of `make clean`
clean() {
	/bin/rm -f -- *.zip ./__init__.py ./conversion/__init__.py ./translations/*.mo plugin-import-name-*.txt
}

# Finds all test files
__all_tests() {
	/usr/bin/find ./tests -maxdepth 1 -type f -name 'test_*.py'
}

# Finds all translation files
__all_translations() {
	/usr/bin/find ./translations -type f -name '*.mo' -exec printf '%s ' '{}' \;
}

# Finds all CSS files
__all_css() {
	/usr/bin/find ./css -type f -exec printf '%s ' '{}' \;
}

# Prints the names of files common to all plugins
__common_files() {
	touch "plugin-import-name-${1}.txt"
	printf './common.py ./__init__.py ./plugin-import-name-%s.txt %s' "${1}" "$(__all_translations)"
}

compile_translations() {
	MSGFMT_BIN="$(command -v msgfmt)"

	while IFS=$'\n' read -r po_file; do
		"${MSGFMT_BIN}" -o "${po_file%%po}mo" "${po_file}"
	done < <(/usr/bin/find translations -type f -name '*.po')
}

# This builds the KoboTouchExtended.zip plugin archive.
build_kte() {
	/bin/cp -f ./device_init.py ./__init__.py

	if [ -r ./KoboTouchExtended.zip ]; then
		zip_args="-u"
	else
		zip_args=""
	fi
	# We explicitly do not want to quote the subcommands here since they all
	# print the file names surrounded in quotes already or refer to a set of
	# CLI flags.
	# shellcheck disable=SC2046,SC2086
	/usr/bin/zip ${zip_args} ./KoboTouchExtended.zip $(__common_files "kobotouch_extended") \
		$(__all_css) ./container.py ./device/*.py

	/bin/rm -f ./__init__.py plugin-import-name-*.txt
}

# This builds the "KePub Output.zip" plugin archive.
build_kepub_output() {
	/bin/cp -f ./conversion_out_init.py ./__init__.py
	/bin/cp -f ./conversion/output_init.py ./conversion/__init__.py

	if [ -r "./KePub Output.zip" ]; then
		zip_args="-u"
	else
		zip_args=""
	fi
	# We explicitly do not want to quote things here since they all print the
	# file names surrounded in quotes already or refer to a set of CLI flags.
	# shellcheck disable=SC2046,SC2086
	/usr/bin/zip ${zip_args} "./KePub Output.zip" $(__common_files "kepubout") \
		$(__all_css) ./conversion/__init__.py ./container.py \
		./conversion/kepub_output.py ./conversion/output_config.py

	/bin/rm -f ./__init__.py ./conversion/__init__.py plugin-import-name-*.txt
}

# This builds the "KePub Input.zip" plugin archive.
build_kepub_input() {
	/bin/cp -f ./conversion_in_init.py ./__init__.py
	/bin/cp -f ./conversion/input_init.py ./conversion/__init__.py

	if [ -r "./KePub Input.zip" ]; then
		zip_args="-u"
	else
		zip_args=""
	fi
	# We explicitly do not want to quote things here since they all print the
	# file names surrounded in quotes already or refer to a set of CLI flags.
	# shellcheck disable=SC2046,SC2086
	/usr/bin/zip ${zip_args} "./KePub Input.zip" $(__common_files "kepubin") \
		./conversion/__init__.py ./container.py ./conversion/kepub_input.py \
		./conversion/input_config.py

	/bin/rm -f ./__init__.py ./conversion/__init__.py plugin-import-name-*.txt
}

# This builds the "KePub Metadata Reader.zip" plugin archive.
build_kepub_md_reader() {
	/bin/cp -f ./md_reader_init.py ./__init__.py

	if [ -r "./KePub Metadata Reader.zip" ]; then
		zip_args="-u"
	else
		zip_args=""
	fi
	# We explicitly do not want to quote things here since they all print the
	# file names surrounded in quotes already or refer to a set of CLI flags.
	# shellcheck disable=SC2046,SC2086
	/usr/bin/zip ${zip_args} "./KePub Metadata Reader.zip" $(__common_files "kepubmdreader") \
		./metadata/__init__.py ./metadata/reader.py

	/bin/rm -f ./__init__.py plugin-import-name-*.txt
}

# This builds the "KePub Metadata Writer.zip" plugin archive.
build_kepub_md_writer() {
	/bin/cp -f ./md_writer_init.py ./__init__.py

	if [ -r "./KePub Metadata Writer.zip" ]; then
		zip_args="-u"
	else
		zip_args=""
	fi
	# We explicitly do not want to quote things here since they all print the
	# file names surrounded in quotes already or refer to a set of CLI flags.
	# shellcheck disable=SC2046,SC2086
	/usr/bin/zip ${zip_args} "./KePub Metadata Writer.zip" $(__common_files "kepubmdwriter") \
		./metadata/__init__.py ./metadata/writer.py

	/bin/rm -f ./__init__.py plugin-import-name-*.txt
}

# Build all plugin ZIP files
build() {
	build_kte
	build_kepub_output
	build_kepub_input
	build_kepub_md_reader
	build_kepub_md_writer
}

cleanup_dir() {
	dname="${1}"

	if [ -n "${dname}" ] && [ -d "${dname}" ]; then
		/bin/rm -rf "${dname}"
	fi
}

# Run tests
# WARNING: You MUST call `build` before running tests!
run_tests() {
	CALIBRE_BIN_BASE="${PWD}/calibre-py3"
	if [ "${PLATFORM}" = "darwin" ]; then
		CALIBRE_BIN_BASE="${CALIBRE_BIN_BASE}/Contents/MacOS"
	fi

	touch ./__init__.py

	if [ -z "${GITHUB_WORKFLOW:-""}" ]; then
		# Not running in Github, create calibre directories
		CALIBRE_DIR="$(mktemp -d XXXXXXXXXXX)"
		/bin/mkdir -p "${CALIBRE_DIR}/config" "${CALIBRE_DIR}/tmp"
		export CALIBRE_CONFIG_DIRECTORY="${CALIBRE_DIR}/config"
		export CALIBRE_TEMP_DIR="${CALIBRE_DIR}/tmp"
	fi

	# Disable quote warning, I want to expand this now since it isn't assured to be defined when
	# called elsewhere, especially at EXIT.
	# shellcheck disable=SC2064
	trap "cleanup_dir ${CALIBRE_DIR:-''}" EXIT INT TERM PIPE

	while IFS=$'\n' read -r plugin; do
		printf 'Installing plugin file "%s" to "%s"\n' "${plugin}" "${CALIBRE_CONFIG_DIRECTORY}"
		"${CALIBRE_BIN_BASE}/calibre-customize" -a "${plugin}"
		"${CALIBRE_BIN_BASE}/calibre-customize" --enable-plugin "$(basename "${plugin%.zip}")"
	done < <(/usr/bin/find . -type f -maxdepth 1 -type f -name '*.zip')

	while IFS=$'\n' read -r test_file; do
		printf 'Executing test: %s\n' "${test_file}"
		PYTHONDONTWRITEBYTECODE="true" "${CALIBRE_BIN_BASE}/calibre-debug" "${test_file}"
	done < <(__all_tests)

	/bin/rm -f ./__init__.py
}

# Update Vale styles
vale_styles() {
	MKTEMP_BIN="$(command -v mktemp)"
	CURL_BIN="$(command -v curl)"
	UNZIP_BIN="$(command -v unzip)"
	STYLE_DIR="$("${MKTEMP_BIN}" -d)"

	for n in Microsoft proselint write-good Joblint; do
		if [ ! -d .github/vale-styles ]; then
			mkdir -p .github/vale-styles
		fi
		if [ -d ".github/vale-styles/${n}" ]; then
			/bin/rm -r ".github/vale-styles/${n}"
		fi

		"${CURL_BIN}" -fsSL "https://github.com/errata-ai/${n}/releases/latest/download/${n}.zip" >"${STYLE_DIR}/${n}.zip"
		"${UNZIP_BIN}" "${STYLE_DIR}/${n}.zip" -d .github/vale-styles
	done

	/bin/rm -r "${STYLE_DIR}"
}


# Check run mode; default if no arguments are given is 'build'
if [ "$#" -eq 0 ]; then
	compile_translations
	build
else
	while [ "$#" -gt 0 ]; do
		OPT="${1}"
		shift
		case "${OPT}" in
			build)
				compile_translations
				build
				;;
			KoboTouchExtended.zip)
				compile_translations
				build_kte
				;;
			test)
				build
				run_tests
				;;
			pot|translations)
				make_pot
				;;
			vale|styles)
				vale_styles
				;;
			clean)
				clean
				;;
		esac
	done
fi
