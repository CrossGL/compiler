#include <iostream>
#include "../headers/lexer.h"

int main(){
    Lexer lex("int abs = 30; float absolute = 222;\n vec3(29,30,40,50);float3(20,30,40);");
    std::vector<Token> types = lex.getTokens();

    std::cout<<"size of the tokens: "<<types.size()<<std::endl;
    for(auto it: types){
        std::cout<<it.value<<" ";
    }
    std::cout<<"\n";
    return 0;
}