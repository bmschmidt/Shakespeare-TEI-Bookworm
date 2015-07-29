all: input.txt .bookworm
	bookworm build all
	bookworm --supplement_metadata --format tsv --file=sp_who_json.txt --key=sp_who

#it just gets built at the same time.

input.txt: TEIfiles
	python TEIparser.py TEIfiles/Folger_Digital_Texts_Complete/*.xml
jsoncatalog.txt: input.txt

#field_descriptions.json is build by hand.

TEIfiles:
	wget -nc http://www.folgerdigitaltexts.org/zip/Folger_Digital_Texts_Complete.zip
	mkdir $@
	unzip Folger_Digital_Texts_Complete.zip -d $@

.bookworm:
	bookworm init

pristine: .bookworm
	bookworm build pristine


