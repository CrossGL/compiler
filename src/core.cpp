#include <iostream>
#include "../headers/lexer.h"

int main(){
    Lexer lex("shader main{\n main(){\n Frag_Color=vec4(10,20,30,10);\n}\n}");
    std::vector<Token> types = lex.getTokens();

    std::cout<<"size of the tokens: "<<types.size()<<std::endl;
    for(auto it: types){
        std::cout<<it.value<<" ";
    }
    std::cout<<"\n";
    return 0;
}