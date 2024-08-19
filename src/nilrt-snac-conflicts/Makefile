.DEFAULT_GOAL := all
.PHONY : all clean


all : nilrt-snac-conflicts.ipk


clean :
	rm -f *.tar.gz
	rm -f *.ipk


control.tar.gz : control
	tar -czf $@ $<


nilrt-snac-conflicts.ipk : control.tar.gz
	tar -czf data.tar.gz -T /dev/null  # make empty data segment
	ar rc $@ $^ data.tar.gz
