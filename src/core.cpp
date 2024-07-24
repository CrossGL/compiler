#include <iostream>
#include "../headers/lexer.h"

int main(){
    Lexer lex("shader main{\nBuffer x = 0;\n Vertex{\n Frag_Color=vec4(10,20,30,10);\n}\n}\nint mix(vec3 x,vec3 y){\nreturn sin(x,y);}\nFragment{\nvoid driver(){}}");
    std::vector<Token> types = lex.getTokens();

    std::cout<<"size of the tokens: "<<types.size()<<std::endl;
    for(auto it: types){
        std::cout<<it.value<<" ";
    }
    std::cout<<"\n";
    return 0;
}