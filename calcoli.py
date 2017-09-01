

class Operazioni():

    def sottrazione(self, text):
        try:
            nums=text.split(" ")
            risultato=int(nums[2])-int(nums[4])
            return(str(risultato))
        except:
            return ("Non ho capito.")
    def somma(self, text):
        try:
            nums=text.split(" ")
            risultato=int(nums[2])+int(nums[4])
            return(str(risultato))
        except:
            return ("Non ho capito.")
    def divisione(self, text):
        try:
            nums=text.split(" ")
            risultato=int(nums[2])/int(nums[4])
            return(str(risultato))
        except:
            return ("Non ho capito.")
    def moltiplicazione(self, text):
        try:
            nums=text.split(" ")
            risultato=int(nums[2])*int(nums[4])
            return(str(risultato))
        except:
            return ("Non ho capito.")