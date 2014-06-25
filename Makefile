



input.txt: TEIfiles
	python TEIparser.py

#it just gets built at the same time.
jsoncatalog.txt: input.txt



TEIfiles:
	wget -nc http://www.folgerdigitaltexts.org/zip/Folger_Digital_Texts_Complete.zip
	mkdir $@
	unzip Folger_Digital_Texts_Complete.zip -d $@

TEIworm:
	git clone git@github.com:bmschmidt/Presidio $@

bookworm: TEIworm/files/texts/input.txt TEIworm/files/metadata/jsoncatalog.txt TEIworm/files/texts/field_descriptions.json
	cd TEIworm; make
	touch $@

TEIworm/bookworm.cnf:
	cd TEIworm; make bookworm.cnf

TEIworm/files/texts/field_descriptions.json: TEIworm TEIworm/files/metadata/jsoncatalog.txt TEIworm/bookworm.cnf
	cd TEIworm; python OneClick.py guessAtFieldDescriptions

TEIworm/files/texts/input.txt: TEIworm input.txt
	mkdir -p $(dir $@)
	ln -fs ../../../input.txt $@

TEIworm/files/metadata/jsoncatalog.txt: TEIworm jsoncatalog.txt
	mkdir -p $(dir $@)
	ln -fs ../../../jsoncatalog.txt $@

clean:
	rm -f TEIworm/files/metadata/* TEIworm/files/texts/input.txt input.txt jsoncatalog.txt bookworm
	cd TEIworm; make pristine;
