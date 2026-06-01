all: clean diagrams

diagrams:
	textx generate odpel.tx --target plantuml --overwrite
	textx generate odppolicy.tx --target plantuml --overwrite
	plantuml *.pu

clean:
	rm *.png || true

